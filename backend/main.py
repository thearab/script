from fastapi import FastAPI

app = FastAPI(title="Ghurfati API")


@app.get("/")
def read_root() -> dict:
    return {"message": "Hello from Ghurfati"}
