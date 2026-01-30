# Ghurfati

AI interior design platform with affiliate product matching.

## Monorepo structure

- `frontend/`: Next.js 14 (App Router), Tailwind CSS, Lucide React.
- `backend/`: FastAPI + Uvicorn API server.
- `scripts/`: reserved for the IKEA scraper.

## Architecture flow

Frontend sends image -> Backend processes with SDXL & ControlNet -> Backend searches Vector DB for IKEA match -> Returns Image + Product Links.

## Supabase configuration

Supabase (PostgreSQL + pgvector) configuration lives in `backend/.env.example` and is used by `backend/supabase_client.py`.
