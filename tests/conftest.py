"""Pytest fixtures and configuration."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app
from app.auth import ensure_user
from db.connection import get_db

TEST_API_KEY = "test-api-key-for-pytest"


@pytest.fixture(scope="session")
def app():
    """Session-scoped Flask application instance."""
    return create_app({"TESTING": True, "DB_NAME": "iot_digital_twin", "API_KEY": TEST_API_KEY})


@pytest.fixture(scope="session")
def client(app):
    """Authenticated test client (sends the API key on every request)."""
    c = app.test_client()
    c.environ_base["HTTP_X_API_KEY"] = TEST_API_KEY
    return c


@pytest.fixture()
def anon_client(app):
    """Test client with no credentials at all."""
    return app.test_client()


@pytest.fixture(scope="session")
def db():
    """MongoDB database fixture."""
    return get_db("iot_digital_twin")


@pytest.fixture()
def test_users(db):
    """Creates one admin and one viewer account for login tests, then removes them."""
    ensure_user(db, "pytest_admin", "AdminPass#123", "admin")
    ensure_user(db, "pytest_viewer", "ViewerPass#123", "viewer")
    yield
    db.users.delete_many({"username": {"$in": ["pytest_admin", "pytest_viewer"]}})
