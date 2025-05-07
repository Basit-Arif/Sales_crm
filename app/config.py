import os


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:basit456@localhost/messenger_crm'  # Default main DB

    # Secondary database binds
    SQLALCHEMY_BINDS = {
        'auth': 'mysql+pymysql://root:basit456@localhost/messenger_crm'
    }
    
    