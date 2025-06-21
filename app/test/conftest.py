import pytest
from app import create_app, db
from flask_migrate import upgrade
from app.config import TestConfig
import sqlalchemy

# ✅ App-wide setup and teardown
@pytest.fixture(scope='module')
def test_app():
    app = create_app(TestConfig)
    app.config['SERVER_NAME'] = 'localhost.localdomain'

    with app.app_context():
        engine = db.engine

        with engine.begin() as conn:
            conn.execute(sqlalchemy.text("SET FOREIGN_KEY_CHECKS=0;"))
            db.metadata.drop_all(bind=engine)
            conn.execute(sqlalchemy.text("SET FOREIGN_KEY_CHECKS=1;"))

        upgrade()
        from sqlalchemy import inspect
        print("📦 Tables in test DB:", inspect(db.engine).get_table_names())

        yield app

        db.session.remove()

# ✅ Provides a fresh session per test function
@pytest.fixture(scope='function')
def db_session(test_app):
    with test_app.app_context():
        yield db.session
        db.session.rollback() # Rollback changes made by each test

@pytest.fixture(scope="module")
def client(test_app):
    return test_app.test_client()












