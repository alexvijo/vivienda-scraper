"""
Basic tests for the search endpoint using mocked HTML.
Run with: pytest tests/ -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

MOCK_HTML = """
<html><body>
  <article class="item">
    <a class="item-link" href="/inmueble/12345/">Piso en Malasaña</a>
    <span class="item-price">350.000 €</span>
    <span class="item-detail">3 hab.</span>
    <span class="item-detail">85 m²</span>
    <img class="item-multimedia" src="https://img.idealista.com/photo.jpg" />
  </article>
  <article class="item">
    <a class="item-link" href="/inmueble/67890/">Ático en Lavapiés</a>
    <span class="item-price">420.000 €</span>
    <span class="item-detail">2 hab.</span>
    <span class="item-detail">70 m²</span>
  </article>
</body></html>
"""


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_platforms():
    resp = client.get("/api/platforms")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    platform_ids = [p["id"] for p in data]
    assert "idealista" in platform_ids


def test_search_missing_city():
    resp = client.get("/api/search")
    assert resp.status_code == 422


def test_search_returns_results():
    with patch("scrapers.idealista_scraper.cloudscraper.create_scraper") as mock_cs:
        mock_instance = MagicMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.text = MOCK_HTML
        mock_instance.get.return_value.raise_for_status = MagicMock()
        mock_cs.return_value = mock_instance

        resp = client.get("/api/search?city=madrid&platforms=idealista")

    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["total"] >= 0


def test_search_price_filter():
    with patch("scrapers.idealista_scraper.cloudscraper.create_scraper") as mock_cs:
        mock_instance = MagicMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.text = MOCK_HTML
        mock_instance.get.return_value.raise_for_status = MagicMock()
        mock_cs.return_value = mock_instance

        resp = client.get("/api/search?city=madrid&price_max=400000&platforms=idealista")

    assert resp.status_code == 200
