import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    MONGO_URI = os.environ.get(
        "MONGO_URI",
        "mongodb://localhost:27017/lab_inventory_db"
    )
