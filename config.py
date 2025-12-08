import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # MySQL configuration for PythonAnywhere (componentsinfo account)
    MYSQL_HOST = os.environ.get("MYSQL_HOST") or "componentsinfo.mysql.pythonanywhere-services.com"
    MYSQL_USER = os.environ.get("MYSQL_USER") or "componentsinfo"
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD") or "Krishna@532"
    MYSQL_DB = os.environ.get("MYSQL_DB") or "componentsinfo$default"
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
