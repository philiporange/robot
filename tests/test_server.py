"""Tests for Robot web server."""

import pytest
from fastapi.testclient import TestClient
from robot.server import app, db, User, Conversation, Message, ModifiedFile


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Register a test user and return auth headers."""
    response = client.post("/api/auth/register", json={
        "username": f"testuser_{id(client)}",
        "password": "testpass123"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_server_import():
    """Test that server module imports correctly."""
    from robot.server import app, User, Conversation, Message
    assert app is not None


def test_register_user(client):
    """Test user registration."""
    import uuid
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    response = client.post("/api/auth/register", json={
        "username": username,
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["username"] == username


def test_login_user(client):
    """Test user login."""
    import uuid
    username = f"testuser_{uuid.uuid4().hex[:8]}"

    # Register first
    client.post("/api/auth/register", json={
        "username": username,
        "password": "password123"
    })

    # Login
    response = client.post("/api/auth/login", json={
        "username": username,
        "password": "password123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "wrongpass"
    })
    assert response.status_code == 401


def test_get_current_user(client, auth_headers):
    """Test getting current user info."""
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert "username" in response.json()


def test_list_folders(client, auth_headers):
    """Test listing folders."""
    response = client.get("/api/folders", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_conversations_empty(client, auth_headers):
    """Test listing conversations when empty."""
    response = client.get("/api/conversations", headers=auth_headers)
    assert response.status_code == 200
    # May have conversations from previous tests


def test_list_models(client, auth_headers):
    """Test listing available models."""
    response = client.get("/api/models", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "claude" in data
    assert any(m["id"] == "opus" for m in data["claude"])


def test_unauthorized_access(client):
    """Test that endpoints require authentication."""
    response = client.get("/api/conversations")
    assert response.status_code in (401, 403)  # Unauthorized


def test_index_returns_html(client):
    """Test that index returns HTML frontend."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Robot" in response.text
