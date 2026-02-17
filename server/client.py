"""PlexClient protocol and implementation for async Plex API operations."""

import asyncio
import os
from typing import Protocol, Any, Dict, List

from plexapi.server import PlexServer
from plexapi.myplex import MyPlexAccount


class PlexClient(Protocol):
    """Protocol defining the async interface for Plex operations.

    This protocol follows the TrueNAS pattern, allowing for easy mocking
    and testing while maintaining a clean separation between the async
    interface and the synchronous plexapi library.
    """

    async def list_libraries(self) -> List[Dict[str, Any]]:
        """List all library sections on the Plex server.

        Returns:
            List of library section dictionaries with keys:
            - key: Section ID
            - title: Section name
            - type: Section type (movie, show, artist, photo)
            - locations: List of filesystem paths
        """
        ...

    async def scan_library(self, section_id: str) -> Dict[str, str]:
        """Trigger a library scan for the specified section.

        Args:
            section_id: The library section ID to scan

        Returns:
            Dictionary with status and section_id

        Raises:
            plexapi.exceptions.NotFound: If section doesn't exist
        """
        ...

    async def search_library(
        self, section_id: str, query: str
    ) -> List[Dict[str, Any]]:
        """Search for items in a library section.

        Args:
            section_id: The library section ID to search
            query: Search query string

        Returns:
            List of matching items with title, year, type, etc.

        Raises:
            plexapi.exceptions.NotFound: If section doesn't exist
        """
        ...

    async def list_recent(
        self, section_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List recently added items in a library section.

        Args:
            section_id: The library section ID
            limit: Maximum number of items to return (default 20)

        Returns:
            List of recently added items with title, year, type, addedAt, etc.

        Raises:
            plexapi.exceptions.NotFound: If section doesn't exist
        """
        ...

    async def get_server_info(self) -> Dict[str, Any]:
        """Get Plex server information.

        Returns:
            Dictionary with server info:
            - name: Server friendly name
            - version: Server version
            - platform: Server platform
            - machineIdentifier: Unique machine ID
        """
        ...

    async def get_library_inventory(self, section_id: str) -> List[Dict[str, Any]]:
        """Get all TV shows in a section with their season numbers.

        Args:
            section_id: The library section ID (must be a 'show' type section)

        Returns:
            List of show dictionaries, each containing:
            - title: Show title
            - year: Premiere year
            - rating_key: Plex rating key (unique ID)
            - seasons: Sorted list of season numbers present (0 = Specials excluded)
            - episode_count: Total episode count across all seasons
        """
        ...

    async def get_show_details(self, rating_key: str) -> Dict[str, Any]:
        """Get detailed season and episode information for a specific show.

        Args:
            rating_key: Plex rating key for the show

        Returns:
            Dictionary with title, year, rating_key, seasons list,
            episode_counts per season dict, and total episode_count.
        """
        ...


class PlexAPIClient:
    """Concrete implementation of PlexClient using plexapi.

    This class wraps the synchronous plexapi library with async methods
    using asyncio.to_thread() to prevent blocking the event loop.
    """

    def __init__(self, server: PlexServer):
        """Initialize with a PlexServer instance.

        Args:
            server: Initialized PlexServer instance
        """
        self.server = server

    async def list_libraries(self) -> List[Dict[str, Any]]:
        """List all library sections on the Plex server."""

        def _sync_list_libraries() -> List[Dict[str, Any]]:
            sections = self.server.library.sections()
            return [
                {
                    "key": section.key,
                    "title": section.title,
                    "type": section.type,
                    "locations": section.locations,
                }
                for section in sections
            ]

        return await asyncio.to_thread(_sync_list_libraries)

    async def scan_library(self, section_id: str) -> Dict[str, str]:
        """Trigger a library scan for the specified section."""

        def _sync_scan_library() -> Dict[str, str]:
            section = self.server.library.section(section_id)
            section.update()
            return {
                "status": "success",
                "section_id": section_id,
            }

        return await asyncio.to_thread(_sync_scan_library)

    async def search_library(
        self, section_id: str, query: str
    ) -> List[Dict[str, Any]]:
        """Search for items in a library section."""

        def _sync_search_library() -> List[Dict[str, Any]]:
            section = self.server.library.section(section_id)
            results = section.search(query)
            return [
                {
                    "title": item.title,
                    "year": getattr(item, "year", None),
                    "type": item.type,
                }
                for item in results
            ]

        return await asyncio.to_thread(_sync_search_library)

    async def list_recent(
        self, section_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List recently added items in a library section."""

        def _sync_list_recent() -> List[Dict[str, Any]]:
            section = self.server.library.section(section_id)
            results = section.recentlyAdded(maxresults=limit)
            return [
                {
                    "title": item.title,
                    "year": getattr(item, "year", None),
                    "type": item.type,
                    "addedAt": getattr(item, "addedAt", None),
                }
                for item in results
            ]

        return await asyncio.to_thread(_sync_list_recent)

    async def get_server_info(self) -> Dict[str, Any]:
        """Get Plex server information."""

        def _sync_get_server_info() -> Dict[str, Any]:
            return {
                "name": self.server.friendlyName,
                "version": self.server.version,
                "platform": self.server.platform,
                "machineIdentifier": self.server.machineIdentifier,
            }

        return await asyncio.to_thread(_sync_get_server_info)

    async def get_library_inventory(self, section_id: str) -> List[Dict[str, Any]]:
        """Get all TV shows with season details from a library section."""

        def _sync_inventory() -> List[Dict[str, Any]]:
            section = self.server.library.section(section_id)
            results = []
            for show in section.all():
                seasons = show.seasons()
                season_numbers = sorted(
                    s.seasonNumber for s in seasons if s.seasonNumber > 0
                )
                episode_count = sum(
                    len(s.episodes()) for s in seasons if s.seasonNumber > 0
                )
                results.append({
                    "title": show.title,
                    "year": getattr(show, "year", None),
                    "rating_key": str(show.ratingKey),
                    "seasons": season_numbers,
                    "episode_count": episode_count,
                })
            return results

        return await asyncio.to_thread(_sync_inventory)

    async def get_show_details(self, rating_key: str) -> Dict[str, Any]:
        """Get detailed season/episode information for a specific show."""

        def _sync_show_details() -> Dict[str, Any]:
            show = self.server.fetchItem(int(rating_key))
            seasons = show.seasons()
            season_numbers = sorted(
                s.seasonNumber for s in seasons if s.seasonNumber > 0
            )
            episode_counts = {
                s.seasonNumber: len(s.episodes())
                for s in seasons
                if s.seasonNumber > 0
            }
            return {
                "title": show.title,
                "year": getattr(show, "year", None),
                "rating_key": str(show.ratingKey),
                "seasons": season_numbers,
                "episode_counts": episode_counts,
                "episode_count": sum(episode_counts.values()),
            }

        return await asyncio.to_thread(_sync_show_details)


def create_plex_client(plex_url: str = None, plex_token: str = None) -> PlexAPIClient:
    """Factory function to create a PlexClient from environment variables or parameters.

    Args:
        plex_url: Plex server URL (defaults to VIDEODROME_PLEX_URL or PLEX_URL env var)
        plex_token: Plex auth token (defaults to VIDEODROME_PLEX_TOKEN or PLEX_TOKEN env var)

    Returns:
        Configured PlexAPIClient instance

    Raises:
        ValueError: If plex_url or plex_token are missing
    """
    # Allow parameters to override environment variables
    if plex_url is None:
        plex_url = os.environ.get("VIDEODROME_PLEX_URL") or os.environ.get("PLEX_URL")
    if plex_token is None:
        plex_token = os.environ.get("VIDEODROME_PLEX_TOKEN") or os.environ.get("PLEX_TOKEN")

    if not plex_url:
        raise ValueError("PLEX_URL environment variable is required")

    if not plex_token:
        raise ValueError("PLEX_TOKEN environment variable is required")

    # Use MyPlexAccount for plex.tv connections (cloud relay)
    if "plex.tv" in plex_url.lower():
        account = MyPlexAccount(token=plex_token)
        # Get the first available server
        resources = account.resources()
        if not resources:
            raise ValueError("No Plex servers found on your account")

        # Connect to the first server
        server = resources[0].connect()
    else:
        # Direct connection to local server
        server = PlexServer(plex_url, plex_token)

    return PlexAPIClient(server)
