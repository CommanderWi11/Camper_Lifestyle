import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import search


def test_make_id_is_deterministic():
    assert search.make_id("wallapop", "https://example.com/item/123") == \
           search.make_id("wallapop", "https://example.com/item/123")


def test_make_id_differs_by_source():
    assert search.make_id("wallapop", "https://x.com") != \
           search.make_id("milanuncios", "https://x.com")


def test_make_id_differs_by_url():
    assert search.make_id("wallapop", "https://x.com/1") != \
           search.make_id("wallapop", "https://x.com/2")


def test_merge_adds_new_listing():
    existing = [{"id": "a-001", "title": "Old", "status": "watching"}]
    new = [{"id": "b-002", "title": "New", "status": "new"}]
    result = search.merge_listings(existing, new)
    assert len(result) == 2


def test_merge_skips_duplicate_id():
    existing = [{"id": "a-001", "title": "Old", "status": "watching"}]
    new = [{"id": "a-001", "title": "Updated", "status": "new"}]
    result = search.merge_listings(existing, new)
    assert len(result) == 1
    assert result[0]["title"] == "Old"


def test_merge_preserves_status():
    existing = [{"id": "a-001", "status": "contacted"}]
    new = [{"id": "a-001", "status": "new"}]
    result = search.merge_listings(existing, new)
    assert result[0]["status"] == "contacted"


def test_merge_deduplicates_within_run():
    existing = []
    new = [
        {"id": "a-001", "title": "First"},
        {"id": "a-001", "title": "Duplicate"},
    ]
    result = search.merge_listings(existing, new)
    assert len(result) == 1
    assert result[0]["title"] == "First"


def test_fetch_wallapop_handles_network_error():
    params = {
        "max_price": 55000,
        "keywords": ["camper"],
        "wallapop": {"latitude": 28.1, "longitude": -15.4, "distance_km": 500},
    }
    with patch("search.requests.get", side_effect=Exception("Network error")):
        results = search.fetch_wallapop(params)
    assert results == []


def test_fetch_wallapop_returns_listings():
    params = {
        "max_price": 55000,
        "keywords": ["camper"],
        "wallapop": {"latitude": 28.1, "longitude": -15.4, "distance_km": 500},
    }
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "search_objects": [{
            "web_slug": "camper-van-12345",
            "title": "Camper Van Test",
            "price": 35000,
            "location": {"city": "Las Palmas"},
            "main_image": {"urls": {"big": "https://img.example.com/photo.jpg"}},
        }]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("search.requests.get", return_value=mock_response):
        results = search.fetch_wallapop(params)

    assert len(results) == 1
    assert results[0]["title"] == "Camper Van Test"
    assert results[0]["price"] == 35000
    assert results[0]["source"] == "wallapop"
    assert results[0]["status"] == "new"


def test_fetch_wallapop_skips_empty_slug():
    """Items with no web_slug should be skipped (they'd all share the same ID)."""
    params = {
        "max_price": 55000,
        "keywords": ["camper"],
        "wallapop": {"latitude": 28.1, "longitude": -15.4, "distance_km": 500},
    }
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "search_objects": [
            {"web_slug": "", "title": "No slug item", "price": 30000, "location": {}},
            {"web_slug": "valid-slug-123", "title": "Valid item", "price": 25000,
             "location": {"city": "Las Palmas"}, "main_image": {"urls": {"big": ""}}},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("search.requests.get", return_value=mock_response):
        results = search.fetch_wallapop(params)

    assert len(results) == 1
    assert results[0]["title"] == "Valid item"


def test_fetch_milanuncios_handles_network_error():
    params = {"max_price": 55000, "keywords": ["camper"]}
    with patch("search.requests.get", side_effect=Exception("Network error")):
        results = search.fetch_milanuncios(params)
    assert results == []
