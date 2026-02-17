"""Tests for library MCP tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Dict, List

from server.tools.library import (
    list_libraries,
    scan_library,
    search_library,
    list_recent,
    get_library_inventory,
    get_show_details,
)


# =============================================================================
# list_libraries Tool Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_libraries_success(mock_async_plex_client):
    """list_libraries should return all library sections."""
    result = await list_libraries(mock_async_plex_client)

    assert isinstance(result, list)
    assert len(result) == 2

    # Verify first library
    assert result[0]["key"] == "1"
    assert result[0]["title"] == "Movies"
    assert result[0]["type"] == "movie"
    assert result[0]["locations"] == ["/data/media/Movies"]

    # Verify second library
    assert result[1]["key"] == "2"
    assert result[1]["title"] == "TV Shows"
    assert result[1]["type"] == "show"
    assert result[1]["locations"] == ["/data/media/TV Shows"]

    mock_async_plex_client.list_libraries.assert_called_once()


@pytest.mark.asyncio
async def test_list_libraries_empty(mock_async_plex_client):
    """list_libraries should handle empty library list."""
    mock_async_plex_client.list_libraries.return_value = []

    result = await list_libraries(mock_async_plex_client)

    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_list_libraries_error_handling(mock_async_plex_client):
    """list_libraries should raise exception on error."""
    mock_async_plex_client.list_libraries.side_effect = Exception("Connection failed")

    with pytest.raises(Exception, match="Connection failed"):
        await list_libraries(mock_async_plex_client)


# =============================================================================
# scan_library Tool Tests
# =============================================================================


@pytest.mark.asyncio
async def test_scan_library_success(mock_async_plex_client):
    """scan_library should trigger library scan."""
    mock_async_plex_client.scan_library = AsyncMock(return_value={
        "status": "success",
        "section_id": "1"
    })

    result = await scan_library(mock_async_plex_client, "1")

    assert result["status"] == "success"
    assert result["section_id"] == "1"

    mock_async_plex_client.scan_library.assert_called_once_with("1")


@pytest.mark.asyncio
async def test_scan_library_invalid_section(mock_async_plex_client):
    """scan_library should handle invalid section ID."""
    from plexapi.exceptions import NotFound

    mock_async_plex_client.scan_library = AsyncMock(
        side_effect=NotFound("Section not found")
    )

    with pytest.raises(NotFound, match="Section not found"):
        await scan_library(mock_async_plex_client, "999")


@pytest.mark.asyncio
async def test_scan_library_string_section_id(mock_async_plex_client):
    """scan_library should accept string section_id."""
    mock_async_plex_client.scan_library = AsyncMock(return_value={
        "status": "success",
        "section_id": "1"
    })

    result = await scan_library(mock_async_plex_client, "1")

    assert result["status"] == "success"
    mock_async_plex_client.scan_library.assert_called_once_with("1")


# =============================================================================
# search_library Tool Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_library_success(mock_async_plex_client):
    """search_library should return matching items."""
    mock_async_plex_client.search_library = AsyncMock(return_value=[
        {
            "title": "Inception",
            "year": 2010,
            "type": "movie"
        }
    ])

    result = await search_library(mock_async_plex_client, "1", "Inception")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["title"] == "Inception"
    assert result[0]["year"] == 2010
    assert result[0]["type"] == "movie"

    mock_async_plex_client.search_library.assert_called_once_with("1", "Inception")


@pytest.mark.asyncio
async def test_search_library_no_results(mock_async_plex_client):
    """search_library should return empty list when no matches found."""
    mock_async_plex_client.search_library = AsyncMock(return_value=[])

    result = await search_library(mock_async_plex_client, "1", "NonExistentMovie")

    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_search_library_invalid_section(mock_async_plex_client):
    """search_library should handle invalid section ID."""
    from plexapi.exceptions import NotFound

    mock_async_plex_client.search_library = AsyncMock(
        side_effect=NotFound("Section not found")
    )

    with pytest.raises(NotFound, match="Section not found"):
        await search_library(mock_async_plex_client, "999", "test")


@pytest.mark.asyncio
async def test_search_library_empty_query(mock_async_plex_client):
    """search_library should handle empty query string."""
    mock_async_plex_client.search_library = AsyncMock(return_value=[])

    result = await search_library(mock_async_plex_client, "1", "")

    assert isinstance(result, list)
    mock_async_plex_client.search_library.assert_called_once_with("1", "")


# =============================================================================
# list_recent Tool Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_recent_success(mock_async_plex_client):
    """list_recent should return recently added items."""
    mock_async_plex_client.list_recent = AsyncMock(return_value=[
        {
            "title": "The Matrix",
            "year": 1999,
            "type": "movie",
            "addedAt": 1609459200
        }
    ])

    result = await list_recent(mock_async_plex_client, "1", 10)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["title"] == "The Matrix"
    assert result[0]["year"] == 1999
    assert result[0]["type"] == "movie"
    assert result[0]["addedAt"] == 1609459200

    mock_async_plex_client.list_recent.assert_called_once_with("1", 10)


@pytest.mark.asyncio
async def test_list_recent_default_limit(mock_async_plex_client):
    """list_recent should use default limit of 20."""
    mock_async_plex_client.list_recent = AsyncMock(return_value=[])

    result = await list_recent(mock_async_plex_client, "1")

    mock_async_plex_client.list_recent.assert_called_once_with("1", 20)


@pytest.mark.asyncio
async def test_list_recent_custom_limit(mock_async_plex_client):
    """list_recent should accept custom limit."""
    mock_async_plex_client.list_recent = AsyncMock(return_value=[])

    result = await list_recent(mock_async_plex_client, "1", 5)

    mock_async_plex_client.list_recent.assert_called_once_with("1", 5)


@pytest.mark.asyncio
async def test_list_recent_invalid_section(mock_async_plex_client):
    """list_recent should handle invalid section ID."""
    from plexapi.exceptions import NotFound

    mock_async_plex_client.list_recent = AsyncMock(
        side_effect=NotFound("Section not found")
    )

    with pytest.raises(NotFound, match="Section not found"):
        await list_recent(mock_async_plex_client, "999", 10)


@pytest.mark.asyncio
async def test_list_recent_empty_library(mock_async_plex_client):
    """list_recent should handle empty library."""
    mock_async_plex_client.list_recent = AsyncMock(return_value=[])

    result = await list_recent(mock_async_plex_client, "1", 10)

    assert isinstance(result, list)
    assert len(result) == 0


# =============================================================================
# get_library_inventory Tool Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_library_inventory_success(mock_async_plex_client):
    """get_library_inventory should return shows with season lists."""
    mock_async_plex_client.get_library_inventory = AsyncMock(return_value=[
        {
            "title": "Breaking Bad",
            "year": 2008,
            "rating_key": "101",
            "seasons": [1, 2, 3, 4, 5],
            "episode_count": 62,
        },
        {
            "title": "Severance",
            "year": 2022,
            "rating_key": "202",
            "seasons": [1],
            "episode_count": 9,
        },
    ])

    result = await get_library_inventory(mock_async_plex_client, "2")

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["title"] == "Breaking Bad"
    assert result[0]["seasons"] == [1, 2, 3, 4, 5]
    assert result[0]["episode_count"] == 62
    mock_async_plex_client.get_library_inventory.assert_called_once_with("2")


@pytest.mark.asyncio
async def test_get_library_inventory_empty_section(mock_async_plex_client):
    """get_library_inventory should return empty list for an empty section."""
    mock_async_plex_client.get_library_inventory = AsyncMock(return_value=[])

    result = await get_library_inventory(mock_async_plex_client, "2")

    assert result == []


@pytest.mark.asyncio
async def test_get_library_inventory_invalid_section(mock_async_plex_client):
    """get_library_inventory should propagate NotFound for invalid sections."""
    from plexapi.exceptions import NotFound

    mock_async_plex_client.get_library_inventory = AsyncMock(
        side_effect=NotFound("Section not found")
    )

    with pytest.raises(NotFound):
        await get_library_inventory(mock_async_plex_client, "999")


# =============================================================================
# get_show_details Tool Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_show_details_success(mock_async_plex_client):
    """get_show_details should return season and episode detail."""
    mock_async_plex_client.get_show_details = AsyncMock(return_value={
        "title": "The Wire",
        "year": 2002,
        "rating_key": "333",
        "seasons": [1, 2, 3, 4, 5],
        "episode_counts": {1: 13, 2: 12, 3: 12, 4: 13, 5: 10},
        "episode_count": 60,
    })

    result = await get_show_details(mock_async_plex_client, "333")

    assert result["title"] == "The Wire"
    assert result["seasons"] == [1, 2, 3, 4, 5]
    assert result["episode_counts"][1] == 13
    assert result["episode_count"] == 60
    mock_async_plex_client.get_show_details.assert_called_once_with("333")
