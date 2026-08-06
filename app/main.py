from fastapi import FastAPI

from app.database.database import engine, Base
from app.models.user import User


app = FastAPI()


@app.get("/")
def home():
    return {
        "message": "Database Connected Successfully!"
    }