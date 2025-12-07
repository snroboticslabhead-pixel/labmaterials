import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    
    # MySQL configuration for PythonAnywhere
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'labmaterial.mysql.pythonanywhere-services.com'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'labmaterial'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or 'Krishna@532'
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'labmaterial$default'
    
    # SQLAlchemy configuration
    SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,  # Recycle connections after 280 seconds
        'pool_pre_ping': True  # Enable connection health checks
    }
