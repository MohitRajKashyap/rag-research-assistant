"""
Integration Tests - Auth and Document API Endpoints
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuthEndpoints:
    async def test_signup_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "NewUser123",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@example.com"
        assert "hashed_password" not in data

    async def test_signup_duplicate_email(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": test_user.email,
            "username": "different",
            "password": "Test1234!",
        })
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    async def test_login_success(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "WrongPassword123",
        })
        assert resp.status_code == 401

    async def test_get_me(self, client: AsyncClient, test_user, auth_headers):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == test_user.email

    async def test_get_me_unauthorized(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 403  # missing auth header

    async def test_refresh_token(self, client: AsyncClient, test_user):
        login = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123",
        })
        refresh_token = login.json()["refresh_token"]
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_change_password(self, client: AsyncClient, test_user, auth_headers):
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "TestPass123", "new_password": "NewPass456"},
            headers=auth_headers,
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestDocumentEndpoints:
    async def test_list_documents_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/documents/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["documents"] == []

    async def test_search_returns_empty_without_index(self, client: AsyncClient, auth_headers):
        from unittest.mock import AsyncMock, patch
        mock_embedding = [0.1] * 1536
        mock_results = []

        with patch("app.api.v1.endpoints.documents.get_embedding_service") as mock_emb, \
             patch("app.api.v1.endpoints.documents.get_vector_store") as mock_vs:
            mock_emb.return_value.embed_text = AsyncMock(return_value=mock_embedding)
            mock_vs.return_value.similarity_search = AsyncMock(return_value=mock_results)

            resp = await client.post(
                "/api/v1/documents/search",
                json={"query": "test query", "top_k": 5},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["total_results"] == 0


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_check(self, client: AsyncClient):
        from unittest.mock import AsyncMock, patch

        with patch("app.api.v1.endpoints.admin.get_vector_store") as mock_vs:
            mock_vs.return_value.get_collection_stats = AsyncMock(return_value={})
            resp = await client.get("/api/v1/health")

        # May be degraded if redis/vector store not running in CI
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data


@pytest.mark.asyncio
class TestAdminEndpoints:
    async def test_admin_list_users_as_admin(self, client: AsyncClient, admin_user, admin_headers):
        resp = await client.get("/api/v1/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        assert "users" in resp.json()

    async def test_admin_list_users_as_regular_user(self, client: AsyncClient, test_user, auth_headers):
        resp = await client.get("/api/v1/admin/users", headers=auth_headers)
        assert resp.status_code == 403
