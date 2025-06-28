import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    SQLALCHEMY_BINDS = {
        'auth': os.getenv("DATABASE_URL")
    }

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL", 
        "mysql+pymysql://admin:12345678@database-2.ccxcuao8gvtq.us-east-1.rds.amazonaws.com/sales_crm_test"
    )
    SQLALCHEMY_BINDS = {
        'auth': os.getenv(
            "TEST_DATABASE_URL",
            "mysql+pymysql://admin:12345678@database-2.ccxcuao8gvtq.us-east-1.rds.amazonaws.com/sales_crm_test"
        )
    }
    SERVER_NAME = "localhost.localdomain"
    assert "sales_crm_test" in SQLALCHEMY_DATABASE_URI, "Test database URL must contain 'sales_crm_test'!"

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Lax'