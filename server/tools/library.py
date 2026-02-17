"""MCP tools for Plex library operations."""

from typing import Any, Dict, List

from server.client import PlexClient



async def list_libraries(client: PlexClient) -> List[Dict[str, Any]]:
    """List all library sections on the Plex server.

    Args:
        client: PlexClient instance

    Returns:
        List of library section dictionaries with keys:
        - key: Section ID
        - title: Section name
        - type: Section type (movie, show, artist, photo)
        - locations: List of filesystem paths

    Example:
        >>> libraries = await list_libraries(client)
        >>> print(libraries[0]["title"])
        Movies
    """
    return await client.list_libraries()


async def scan_library(client: PlexClient, section_id: str) -> Dict[str, str]:
    """Trigger a library scan for the specified section.

    This initiates a scan of the library section to detect new or changed media files.

    Args:
        client: PlexClient instance
        section_id: The library section ID to scan

    Returns:
        Dictionary with status and section_id

    Raises:
        plexapi.exceptions.NotFound: If section doesn't exist

    Example:
        >>> result = await scan_library(client, "1")
        >>> print(result["status"])
        success
    """
    return await client.scan_library(section_id)


async def search_library(
    client: PlexClient, section_id: str, query: str
) -> List[Dict[str, Any]]:
    """Search for items in a library section.

    Args:
        client: PlexClient instance
        section_id: The library section ID to search
        query: Search query string

    Returns:
        List of matching items with title, year, type, etc.

    Raises:
        plexapi.exceptions.NotFound: If section doesn't exist

    Example:
        >>> results = await search_library(client, "1", "Inception")
        >>> print(results[0]["title"])
        Inception
    """
    return await client.search_library(section_id, query)


async def list_recent(
    client: PlexClient, section_id: str, limit: int = 20
) -> List[Dict[str, Any]]:
    """List recently added items in a library section.

    Args:
        client: PlexClient instance
        section_id: The library section ID
        limit: Maximum number of items to return (default 20)

    Returns:
        List of recently added items with title, year, type, addedAt, etc.

    Raises:
        plexapi.exceptions.NotFound: If section doesn't exist

    Example:
        >>> recent = await list_recent(client, "1", 10)
        >>> print(len(recent))
        10
    """
    return await client.list_recent(section_id, limit)


async def get_library_inventory(
    client: PlexClient, section_id: str
) -> List[Dict[str, Any]]:
    """Get all TV shows in a section with their season numbers.

    Use this to understand which seasons are already in Plex before
    comparing against TMDb to find missing seasons.

    Args:
        client: PlexClient instance
        section_id: The library section ID (should be a 'show' type section)

    Returns:
        List of show dictionaries, each containing:
        - title: Show title
        - year: Premiere year
        - rating_key: Plex rating key
        - seasons: Sorted list of season numbers present (Specials/Season 0 excluded)
        - episode_count: Total episode count across all seasons

    Example:
        >>> inventory = await get_library_inventory(client, "2")
        >>> print(inventory[0]["seasons"])
        [1, 2, 3]
    """
    return await client.get_library_inventory(section_id)


async def get_show_details(
    client: PlexClient, rating_key: str
) -> Dict[str, Any]:
    """Get detailed season and episode information for a specific TV show.

    Args:
        client: PlexClient instance
        rating_key: Plex rating key for the show (from search_library or get_library_inventory)

    Returns:
        Dictionary with:
        - title: Show title
        - year: Premiere year
        - rating_key: Plex rating key
        - seasons: Sorted list of season numbers
        - episode_counts: Dict mapping season number to episode count
        - episode_count: Total episode count

    Example:
        >>> details = await get_show_details(client, "12345")
        >>> print(details["episode_counts"])
        {1: 10, 2: 12, 3: 8}
    """
    return await client.get_show_details(rating_key)
