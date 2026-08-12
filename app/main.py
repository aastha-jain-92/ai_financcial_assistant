from fastapi import FastAPI

from app.database.database import engine, Base
from app.models.user import User
from app.api.auth import router as auth_router

app = FastAPI()
app.include_router(auth_router)

@app.get("/")
def home():
    return {
        "message": "Database Connected Successfully!"
    }