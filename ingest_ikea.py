#!/usr/bin/env python3
"""IKEA UAE sofa scraper + CLIP embedding ingestion.

Lightweight extraction with requests/BeautifulSoup and a JS-rendering fallback note.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import signal
import sys
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image
from sentence_transformers import SentenceTransformer
from supabase import Client, create_client
from tqdm import tqdm

BASE_URL = "https://www.ikea.com/ae/en"
CATEGORY_PATH = "/cat/sofas-10660/"
CATEGORY_URL = f"{BASE_URL}{CATEGORY_PATH}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

SELECTORS = {
    "product_card": [
        "div.product-compact",
        "div.product-compact__spacer",
        "div.pip-product-list__item",
        "div.plp-product-list__item",
    ],
    "title": [
        "span.product-compact__name",
        "h3.product-compact__name",
        "h3.pip-header-section__title--big",
        "a.pip-product-compact__link span",
    ],
    "final_price": [
        "span.product-compact__price__integer",
        "span.product-compact__price",
        "span.pip-price__integer",
        "span.pip-price",
    ],
    "original_price": [
        "span.product-compact__price--original",
        "span.pip-price__original-price",
        "span.pip-price-module__original-price",
    ],
    "link": [
        "a.product-compact__link",
        "a.pip-product-compact__link",
        "a.pip-product-compact",
    ],
    "image": [
        "img.product-compact__image",
        "img.pip-product-compact__image",
        "img.pip-image",
    ],
    "article_number": [
        "span.product-compact__type-number",
        "span.pip-product-compact__description",
        "span.pip-product-compact__type-number",
    ],
}

ARTICLE_NUMBER_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{2}\b")


@dataclass
class ProductRecord:
    title: str
    final_price: Optional[float]
    original_price: Optional[float]
    product_url: str
    image_url: Optional[str]
    article_number: Optional[str]


class GracefulExit(Exception):
    pass


def handle_sigint(_signum, _frame):
    raise GracefulExit


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_supabase() -> Client:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY/ANON_KEY in .env")
    return create_client(url, key)


def normalize_price(raw: str | None) -> Optional[float]:
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.]", "", raw)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def select_first(soup: BeautifulSoup, selectors: Iterable[str]):
    for selector in selectors:
        match = soup.select_one(selector)
        if match:
            return match
    return None


def extract_article_number(text: str | None) -> Optional[str]:
    if not text:
        return None
    match = ARTICLE_NUMBER_PATTERN.search(text)
    return match.group(0) if match else None


def parse_product_card(card: BeautifulSoup) -> ProductRecord:
    title_el = select_first(card, SELECTORS["title"])
    title = title_el.get_text(strip=True) if title_el else ""

    price_el = select_first(card, SELECTORS["final_price"])
    final_price = normalize_price(price_el.get_text(" ", strip=True) if price_el else None)

    original_el = select_first(card, SELECTORS["original_price"])
    original_price = normalize_price(
        original_el.get_text(" ", strip=True) if original_el else None
    )

    link_el = select_first(card, SELECTORS["link"])
    link = urljoin(BASE_URL, link_el["href"]) if link_el and link_el.get("href") else ""

    image_el = select_first(card, SELECTORS["image"])
    image_url = None
    if image_el:
        image_url = image_el.get("src") or image_el.get("data-src")
        if image_url:
            image_url = urljoin(BASE_URL, image_url)

    article_el = select_first(card, SELECTORS["article_number"])
    article_number = extract_article_number(
        article_el.get_text(" ", strip=True) if article_el else None
    )

    if not article_number and link:
        article_number = extract_article_number(link)

    return ProductRecord(
        title=title,
        final_price=final_price,
        original_price=original_price,
        product_url=link,
        image_url=image_url,
        article_number=article_number,
    )


def fetch_page(url: str, session: requests.Session) -> BeautifulSoup:
    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def fetch_product_cards(page: BeautifulSoup) -> list[BeautifulSoup]:
    for selector in SELECTORS["product_card"]:
        cards = page.select(selector)
        if cards:
            return cards
    return []


def build_page_url(page_number: int) -> str:
    if page_number <= 1:
        return CATEGORY_URL
    return f"{CATEGORY_URL}?page={page_number}"


def download_image(url: str, session: requests.Session) -> BytesIO:
    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BytesIO(response.content)


def generate_embedding(model: SentenceTransformer, image_bytes: BytesIO) -> list[float]:
    image = Image.open(image_bytes).convert("RGB")
    vector = model.encode(image)
    return vector.tolist()


def deduplicate(supabase: Client, product_url: str, article_number: Optional[str]) -> bool:
    if product_url:
        existing = (
            supabase.table("ikea_products")
            .select("id")
            .eq("product_url", product_url)
            .limit(1)
            .execute()
        )
        if existing.data:
            return True

    if article_number:
        existing = (
            supabase.table("ikea_products")
            .select("id")
            .eq("article_number", article_number)
            .limit(1)
            .execute()
        )
        if existing.data:
            return True

    return False


def save_product(
    supabase: Client,
    product: ProductRecord,
    embedding: list[float],
    category: str,
) -> None:
    payload = {
        "title": product.title,
        "price_final": product.final_price,
        "price_original": product.original_price,
        "product_url": product.product_url,
        "image_url": product.image_url,
        "article_number": product.article_number,
        "embedding": embedding,
        "metadata": {
            "category": category,
            "store_location": "UAE",
            "currency": "AED",
        },
    }
    supabase.table("ikea_products").insert(payload).execute()


def log_js_fallback_hint() -> None:
    logging.info(
        "If IKEA renders products via JS, consider using Playwright or Selenium as a "
        "fallback for HTML rendering before parsing."
    )


def main() -> int:
    setup_logging()
    signal.signal(signal.SIGINT, handle_sigint)

    model = SentenceTransformer("sentence-transformers/clip-ViT-B-32")
    supabase = load_supabase()

    session = requests.Session()
    products: list[ProductRecord] = []

    try:
        for page_number in range(1, 6):
            page_url = build_page_url(page_number)
            page = fetch_page(page_url, session)
            cards = fetch_product_cards(page)
            if not cards:
                log_js_fallback_hint()
                break

            logging.info("Found %s products on page %s", len(cards), page_number)
            for card in cards:
                product = parse_product_card(card)
                if product.title and product.product_url:
                    products.append(product)

            time.sleep(random.uniform(1.0, 2.5))

        if not products:
            logging.warning("No products collected; stopping.")
            return 0

        for product in tqdm(products, desc="Processing products"):
            if not product.image_url:
                logging.warning("Skipping %s due to missing image.", product.title)
                continue

            if deduplicate(supabase, product.product_url, product.article_number):
                logging.info("Skipping duplicate %s", product.title)
                continue

            image_bytes = download_image(product.image_url, session)
            embedding = generate_embedding(model, image_bytes)
            logging.info("Image processed for %s", product.title)

            save_product(supabase, product, embedding, "Living Room / Sofas")
            logging.info("Successfully saved to DB: %s", product.title)

    except GracefulExit:
        logging.info("Interrupted by user, exiting cleanly.")
        return 130
    except requests.RequestException as exc:
        logging.error("Network error: %s", exc)
        return 1
    except Exception as exc:
        logging.error("Unhandled error: %s", exc)
        return 1
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
