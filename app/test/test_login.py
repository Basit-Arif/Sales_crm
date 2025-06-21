import pytest
from flask import url_for
from app.models import User
from app.services.helper_function import generate_token
from werkzeug.security import generate_password_hash
from app.extension import db
from app.services.helper_function import send_reset_email
from app.models.models import User as UserModel

@pytest.fixture
def test_user(db_session):
    user = User(username="test", email="test@example.com", password="hashed")
    db_session.add(user)
    db_session.commit()
    return user

def test_forgot_password_valid_email(client, test_user):
    response = client.post(
        url_for('auth.forgot_password'),
        data={'email': test_user.email},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"reset link has been sent" in response.data


def test_forgot_password_invalid_email(client):
    response = client.post(
        url_for('auth.forgot_password'),
        data={'email': 'nonexistent@example.com'},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"email not found" in response.data or b"reset link has been sent" in response.data


def test_reset_password_valid_token(client, db_session, test_user):
    token = generate_token(test_user.username)
    response = client.post(
        url_for('auth.reset_password', token=token),
        data={'password': 'new_secure_password'},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Password successfully updated" in response.data


def test_reset_password_invalid_token(client):
    response = client.get(url_for('auth.reset_password', token="invalidtoken"), follow_redirects=True)
    assert response.status_code == 200
    assert b"reset link is invalid or has expired" in response.data