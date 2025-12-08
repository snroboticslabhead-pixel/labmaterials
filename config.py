import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    
    # MySQL configuration for PythonAnywhere
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'labmaterial.mysql.pythonanywhere-services.com'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'labmaterial'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or 'Krishna@532'
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'labmaterial$default'
