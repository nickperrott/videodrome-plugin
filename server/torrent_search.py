"""TorrentSearchClient wrapping torrent-search-mcp for use within videodrome."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TorrentSearchClient:
    """
    Wraps the torrent-search-mcp library for use within videodrome.

    Gracefully degrades when torrent-search-mcp is not installed — all
    methods return an error dict rather than raising ImportError.

    Providers (configured via TORRENT_SEARCH_PROVIDERS env var):
        - thepiratebay
        - nyaa
        - ygg  (requires YGG_USERNAME / YGG_PASSWORD)
    """

    def __init__(self, providers: List[str] = None):
        self.providers = providers or ["thepiratebay"]
        self._provider_aliases = {
            "thepiratebay": {"thepiratebay", "tpb", "thepiratebay.org"},
            "nyaa": {"nyaa", "nyaa.si"},
            "ygg": {"ygg", "yggtorrent", "www.yggtorrent.ms"},
        }
        self._is_available = False
        self._api = None

    def connect(self) -> bool:
        """Verify torrent-search-mcp is importable."""
        try:
            from torrent_search.wrapper import TorrentSearchApi  # noqa: F401
            self._is_available = True
            logger.info("TorrentSearchClient ready (providers: %s)", self.providers)
            return True
        except ImportError:
            logger.warning(
                "torrent-search-mcp not installed — torrent search unavailable. "
                "Install with: pip install torrent-search-mcp"
            )
            return False

    def _get_api(self):
        if self._api is None:
            from torrent_search.wrapper import TorrentSearchApi
            self._api = TorrentSearchApi()
        return self._api

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for torrents by query string.

        Returns list of normalised result dicts with keys:
            id, title, source, size, seeders, leechers, date, magnet
        """
        api = self._get_api()
        results = await api.search_torrents(query, max_items=limit)
        normalised = [self._normalise(r) for r in (results or [])]

        if self.providers:
            normalised = [r for r in normalised if self._is_provider_allowed(r.get("source", ""))]

        return normalised[:limit]

    async def get_magnet(self, torrent_id: str) -> Optional[str]:
        """
        Resolve a torrent ID to its magnet URI.

        Args:
            torrent_id: ID string returned by search()

        Returns:
            Magnet URI string, or None if unavailable.
        """
        api = self._get_api()
        result = await api.get_torrent(torrent_id)
        # Returns a magnet URI string or torrent file path
        if result and result.startswith("magnet:"):
            return result
        return result  # may be a .torrent file path

    @staticmethod
    def _normalise(raw) -> Dict[str, Any]:
        # raw is a Torrent pydantic model (torrent_search.wrapper.models.Torrent)
        if hasattr(raw, "model_dump"):
            data = raw.model_dump()
        elif isinstance(raw, dict):
            data = raw
        else:
            data = vars(raw)
        return {
            "id": data.get("id", ""),
            "title": data.get("filename", data.get("title", "")),
            "source": data.get("source", ""),
            "size": data.get("size", ""),
            "seeders": int(data.get("seeders") or 0),
            "leechers": int(data.get("leechers") or 0),
            "date": data.get("date", ""),
            "magnet": data.get("magnet_link", data.get("magnet")),
        }

    def _is_provider_allowed(self, source: str) -> bool:
        """Return True when source matches the configured provider allow-list."""
        if not self.providers:
            return True

        source_key = str(source or "").strip().lower()
        allowed_aliases = set()
        for provider in self.providers:
            provider_key = str(provider or "").strip().lower()
            allowed_aliases.update(self._provider_aliases.get(provider_key, {provider_key}))

        return source_key in allowed_aliases

    @staticmethod
    def rank(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort results: season packs first, then by seeder count descending.

        Season packs are identified by keywords in the title:
            complete, season, s0, pack
        """
        def _score(r: Dict[str, Any]) -> int:
            pack_bonus = 1000 if any(
                kw in r["title"].lower()
                for kw in ("complete", "season", " pack", "collection")
            ) else 0
            return pack_bonus + r["seeders"]

        return sorted(results, key=_score, reverse=True)
