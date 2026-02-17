"""Tests for torrent search client and tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from server.torrent_search import TorrentSearchClient
from server.tools.torrent_search import (
    search_torrents,
    get_torrent_magnet,
    search_season,
    _resolve_language,
    _build_language_queries,
    _rank_with_language,
)


# =============================================================================
# TorrentSearchClient unit tests
# =============================================================================


def test_connect_returns_false_when_library_not_installed():
    """connect() should return False gracefully when torrent-search-mcp is absent."""
    client = TorrentSearchClient()
    with patch.dict("sys.modules", {"torrent_search": None}):
        result = client.connect()
    assert result is False
    assert client.is_available is False


def test_connect_returns_true_when_library_present():
    """connect() should return True and set is_available when library is importable."""
    client = TorrentSearchClient()
    mock_module = MagicMock()
    mock_module.TorrentSearch = MagicMock()
    with patch.dict("sys.modules", {"torrent_search": mock_module}):
        result = client.connect()
    assert result is True
    assert client.is_available is True


@pytest.mark.asyncio
async def test_client_search_filters_to_configured_providers():
    """search() should keep only results from configured providers."""
    client = TorrentSearchClient(providers=["thepiratebay"])
    client._is_available = True

    mock_ts = MagicMock()
    mock_ts.search.return_value = [
        {"id": "a", "title": "TPB result", "source": "tpb", "seeders": 10},
        {"id": "b", "title": "Nyaa result", "source": "nyaa", "seeders": 20},
    ]
    mock_module = MagicMock()
    mock_module.TorrentSearch = MagicMock(return_value=mock_ts)

    with patch.dict("sys.modules", {"torrent_search": mock_module}):
        results = await client.search("test", limit=10)

    assert len(results) == 1
    assert results[0]["source"] == "tpb"


@pytest.mark.asyncio
async def test_client_search_falls_back_when_provider_kw_not_supported():
    """search() should retry without provider kwarg on older torrent-search versions."""
    client = TorrentSearchClient(providers=["nyaa"])
    client._is_available = True

    mock_ts = MagicMock()

    def fake_search(*args, **kwargs):
        if "providers" in kwargs:
            raise TypeError("unexpected keyword argument 'providers'")
        return [{"id": "n1", "title": "Nyaa result", "source": "nyaa", "seeders": 15}]

    mock_ts.search.side_effect = fake_search
    mock_module = MagicMock()
    mock_module.TorrentSearch = MagicMock(return_value=mock_ts)

    with patch.dict("sys.modules", {"torrent_search": mock_module}):
        results = await client.search("anime", limit=5)

    assert len(results) == 1
    assert results[0]["source"] == "nyaa"
    assert mock_ts.search.call_count == 2


def test_rank_prefers_season_packs():
    """rank() should place season packs above individual episodes."""
    results = [
        {"id": "1", "title": "Breaking Bad S05E01", "seeders": 100},
        {"id": "2", "title": "Breaking Bad Season 5 Complete", "seeders": 50},
        {"id": "3", "title": "Breaking Bad S05 Complete Pack", "seeders": 30},
    ]
    ranked = TorrentSearchClient.rank(results)
    # Both "Complete" and "Pack" should score above the single episode
    pack_ids = {r["id"] for r in ranked[:2]}
    assert "2" in pack_ids
    assert "3" in pack_ids


def test_rank_sorts_by_seeders_within_same_category():
    """rank() should sort by seeder count when pack status is equal."""
    results = [
        {"id": "1", "title": "Show Season 1 Complete", "seeders": 10},
        {"id": "2", "title": "Show Season 1 Complete", "seeders": 200},
        {"id": "3", "title": "Show Season 1 Complete", "seeders": 50},
    ]
    ranked = TorrentSearchClient.rank(results)
    assert ranked[0]["id"] == "2"
    assert ranked[1]["id"] == "3"
    assert ranked[2]["id"] == "1"


def test_normalise_handles_missing_fields():
    """_normalise() should default missing fields gracefully."""
    raw = {"id": "abc", "title": "Test"}
    result = TorrentSearchClient._normalise(raw)
    assert result["id"] == "abc"
    assert result["title"] == "Test"
    assert result["seeders"] == 0
    assert result["leechers"] == 0
    assert result["magnet"] is None


def test_normalise_casts_seeders_to_int():
    """_normalise() should cast seeders/leechers to int."""
    raw = {"id": "x", "title": "T", "seeders": "42", "leechers": "7"}
    result = TorrentSearchClient._normalise(raw)
    assert result["seeders"] == 42
    assert result["leechers"] == 7


# =============================================================================
# Tool function tests
# =============================================================================


@pytest.fixture
def available_client():
    client = MagicMock(spec=TorrentSearchClient)
    client.is_available = True
    return client


@pytest.fixture
def unavailable_client():
    client = MagicMock(spec=TorrentSearchClient)
    client.is_available = False
    return client


@pytest.mark.asyncio
async def test_search_torrents_unavailable_returns_error(unavailable_client):
    """search_torrents should return an error dict when library not installed."""
    result = await search_torrents(unavailable_client, "test query")
    assert "error" in result


@pytest.mark.asyncio
async def test_search_torrents_returns_ranked_results(available_client):
    """search_torrents should return ranked results with total count."""
    mock_results = [
        {"id": "1", "title": "Show Season 1 Complete", "seeders": 50, "leechers": 5,
         "source": "tpb", "size": "5 GB", "date": "2024-01-01", "magnet": None},
        {"id": "2", "title": "Show S01E01", "seeders": 200, "leechers": 10,
         "source": "tpb", "size": "1 GB", "date": "2024-01-01", "magnet": None},
    ]
    available_client.search = AsyncMock(return_value=mock_results)

    with patch.object(TorrentSearchClient, "rank", return_value=mock_results):
        result = await search_torrents(available_client, "Show Season 1")

    assert "results" in result
    assert "total" in result
    assert result["query"] == "Show Season 1"
    available_client.search.assert_called_once_with("Show Season 1", limit=10)


@pytest.mark.asyncio
async def test_get_torrent_magnet_unavailable_returns_error(unavailable_client):
    """get_torrent_magnet should return error dict when library not installed."""
    result = await get_torrent_magnet(unavailable_client, "abc123")
    assert "error" in result


@pytest.mark.asyncio
async def test_get_torrent_magnet_returns_magnet(available_client):
    """get_torrent_magnet should return the magnet URI."""
    expected_magnet = "magnet:?xt=urn:btih:abc123&dn=Test+Show"
    available_client.get_magnet = AsyncMock(return_value=expected_magnet)

    result = await get_torrent_magnet(available_client, "abc123")

    assert result["magnet"] == expected_magnet
    assert result["torrent_id"] == "abc123"


@pytest.mark.asyncio
async def test_get_torrent_magnet_not_found(available_client):
    """get_torrent_magnet should return error when magnet cannot be resolved."""
    available_client.get_magnet = AsyncMock(return_value=None)

    result = await get_torrent_magnet(available_client, "missing-id")

    assert "error" in result


@pytest.mark.asyncio
async def test_search_season_unavailable_returns_error(unavailable_client):
    """search_season should return error dict when library not installed."""
    result = await search_season(unavailable_client, "Ted Lasso", 3)
    assert "error" in result


@pytest.mark.asyncio
async def test_search_season_deduplicates_results(available_client):
    """search_season should not return duplicate IDs from multi-query search."""
    shared_result = {
        "id": "dup-id", "title": "Ted Lasso Season 3 Complete 1080p",
        "seeders": 100, "leechers": 5, "source": "tpb",
        "size": "10 GB", "date": "2024-01-01", "magnet": None,
    }
    # Both queries return the same result
    available_client.search = AsyncMock(return_value=[shared_result])

    result = await search_season(available_client, "Ted Lasso", 3)

    # Should appear only once despite two queries
    ids = [r["id"] for r in result["results"]]
    assert ids.count("dup-id") == 1


@pytest.mark.asyncio
async def test_search_season_structure(available_client):
    """search_season should return expected keys."""
    available_client.search = AsyncMock(return_value=[])

    result = await search_season(available_client, "Severance", 2, quality="720p")

    assert result["show"] == "Severance"
    assert result["season"] == 2
    assert result["quality"] == "720p"
    assert "results" in result
    assert "total" in result


# =============================================================================
# Language helper unit tests
# =============================================================================


def test_resolve_language_german_name():
    """_resolve_language should map 'german' to 'de'."""
    assert _resolve_language("german") == "de"


def test_resolve_language_iso_code():
    """_resolve_language should accept 'de' directly."""
    assert _resolve_language("de") == "de"


def test_resolve_language_case_insensitive():
    """_resolve_language should be case-insensitive."""
    assert _resolve_language("German") == "de"
    assert _resolve_language("FRENCH") == "fr"


def test_resolve_language_english_returns_none():
    """_resolve_language should return None for English (default language)."""
    assert _resolve_language("english") is None
    assert _resolve_language("en") is None


def test_resolve_language_none_input():
    """_resolve_language should return None when no language given."""
    assert _resolve_language(None) is None


def test_resolve_language_unknown_returns_none():
    """_resolve_language should return None for unrecognised language."""
    assert _resolve_language("klingon") is None


def test_build_language_queries_german_adds_keywords():
    """_build_language_queries for 'de' should append German keywords to base queries."""
    base = ["Dark Season 1 1080p"]
    result = _build_language_queries(base, "de")

    # Should include at least two language-augmented variants
    assert any("German" in q for q in result)
    assert any("Deutsch" in q for q in result)


def test_build_language_queries_german_adds_staffel():
    """_build_language_queries for 'de' should add a Staffel N variant."""
    base = ["Dark Season 1 1080p"]
    result = _build_language_queries(base, "de")

    assert any("Staffel 1" in q for q in result)


def test_build_language_queries_french_adds_saison():
    """_build_language_queries for 'fr' should add Saison N variant."""
    base = ["Call My Agent Season 2 1080p"]
    result = _build_language_queries(base, "fr")

    assert any("Saison 2" in q for q in result)


def test_build_language_queries_no_duplicates():
    """_build_language_queries should not return duplicate queries."""
    base = ["Show S01 1080p"]
    result = _build_language_queries(base, "de")

    assert len(result) == len(set(result))


def test_rank_with_language_prefers_german_tagged():
    """_rank_with_language should place GERMAN-tagged results above untagged."""
    results = [
        {"id": "1", "title": "Dark S01 Complete 1080p", "seeders": 500},
        {"id": "2", "title": "Dark S01 GERMAN Complete 1080p", "seeders": 100},
    ]
    ranked = _rank_with_language(results, "de")

    assert ranked[0]["id"] == "2"  # German-tagged despite lower seeders


def test_rank_with_language_none_falls_back_to_seeders():
    """_rank_with_language with no language should rank purely by seeders (+ pack bonus)."""
    results = [
        {"id": "1", "title": "Show Complete Season 1", "seeders": 50},
        {"id": "2", "title": "Show S01E01", "seeders": 200},
    ]
    ranked = _rank_with_language(results, None)

    # "Complete Season" → pack bonus → should win even with fewer seeders
    assert ranked[0]["id"] == "1"


# =============================================================================
# Language parameter integration tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_season_german_includes_staffel_query(available_client):
    """search_season with language='german' should issue a Staffel N query."""
    available_client.search = AsyncMock(return_value=[])

    await search_season(available_client, "Dark", 1, language="german")

    # Collect all query strings that were passed to client.search
    call_args_list = available_client.search.call_args_list
    queries_used = [call[0][0] for call in call_args_list]

    assert any("Staffel 1" in q for q in queries_used)


@pytest.mark.asyncio
async def test_search_season_language_response_includes_keys(available_client):
    """search_season with a language should include 'language' and 'indexer_tip' in response."""
    available_client.search = AsyncMock(return_value=[])

    result = await search_season(available_client, "Dark", 1, language="de")

    assert result["language"] == "de"
    assert "indexer_tip" in result


@pytest.mark.asyncio
async def test_search_torrents_language_response_keys(available_client):
    """search_torrents with a language should include 'language' and 'indexer_tip'."""
    available_client.search = AsyncMock(return_value=[])

    result = await search_torrents(available_client, "Dark", language="de")

    assert result["language"] == "de"
    assert "indexer_tip" in result


@pytest.mark.asyncio
async def test_search_torrents_english_no_language_key(available_client):
    """search_torrents without language should not include 'language' key."""
    available_client.search = AsyncMock(return_value=[])

    result = await search_torrents(available_client, "Breaking Bad")

    assert "language" not in result
