import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.providers.google import close_http_clients

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_http_clients()


app = FastAPI(
    title="AI Financial Assistant",
    lifespan=lifespan,
)

app.include_router(auth_router)


@app.get("/")
def home():
    return {
        "message": "Database Connected Successfully!"
    }


@app.get("/health")
def health():
    return {"status": "ok"}
