"""Torrent search tool functions for videodrome MCP."""

from typing import Any, Dict, List, Optional

from server.torrent_search import TorrentSearchClient

_UNAVAILABLE = {"error": "Torrent search not available (torrent-search-mcp not installed). "
                         "Run: pip install 'torrent-search-mcp>=1.1.0' && playwright install --with-deps chromium"}

# ---------------------------------------------------------------------------
# Language query helpers
# ---------------------------------------------------------------------------

# Language code → (display name, query keywords, release group patterns)
_LANGUAGE_CONFIG: Dict[str, Dict[str, Any]] = {
    "de": {
        "name": "German",
        "keywords": ["German", "Deutsch", "GERMAN"],
        # Common German release patterns that appear in torrent titles
        "release_patterns": ["GERMAN", "German", "Deutsch", "DUAL.German", "GER"],
        # German word for "Season" — enables native-language searches
        "season_word": "Staffel",
        # Well-known German-language torrent indexers (for user reference)
        "indexer_notes": (
            "For German content, consider adding these indexers to Jackett/Prowlarr: "
            "Boerse.bz (private), Knaben (DHT aggregator). "
            "1337x and TPB also carry GERMAN-tagged releases."
        ),
    },
    "fr": {
        "name": "French",
        "keywords": ["French", "FRENCH", "VFF", "TRUEFRENCH"],
        "release_patterns": ["FRENCH", "VFF", "TRUEFRENCH"],
        "season_word": "Saison",
        "indexer_notes": (
            "For French content, YggTorrent (ygg provider) is the primary source — "
            "set YGG_USERNAME and YGG_PASSWORD in your .env."
        ),
    },
    "es": {
        "name": "Spanish",
        "keywords": ["Spanish", "SPANISH", "CASTELLANO"],
        "release_patterns": ["SPANISH", "CASTELLANO", "ESP"],
        "season_word": "Temporada",
        "indexer_notes": "ThePirateBay and 1337x carry Spanish-tagged releases.",
    },
    "it": {
        "name": "Italian",
        "keywords": ["Italian", "ITALIAN", "ITA"],
        "release_patterns": ["ITALIAN", "ITA"],
        "season_word": "Stagione",
        "indexer_notes": "ThePirateBay and 1337x carry Italian-tagged releases.",
    },
    "ja": {
        "name": "Japanese",
        "keywords": ["Japanese", "JPN"],
        "release_patterns": ["JPN", "Japanese"],
        "season_word": "Season",  # Japanese releases typically use English "Season"
        "indexer_notes": "Nyaa (nyaa provider) is the primary Japanese anime/content source.",
    },
}

# Normalise user input → ISO code
_LANGUAGE_ALIASES: Dict[str, str] = {
    "german": "de", "deutsch": "de", "de": "de",
    "french": "fr", "français": "fr", "fr": "fr",
    "spanish": "es", "español": "es", "es": "es",
    "italian": "it", "italiano": "it", "it": "it",
    "japanese": "ja", "jp": "ja", "ja": "ja",
    "english": "en", "en": "en",
}


def _resolve_language(lang: Optional[str]) -> Optional[str]:
    """Normalise a language name or code to a lowercase ISO code, or None for English."""
    if not lang:
        return None
    code = _LANGUAGE_ALIASES.get(lang.lower().strip())
    return code if code and code != "en" else None


def _build_language_queries(
    base_queries: List[str],
    lang_code: str,
) -> List[str]:
    """
    Append language-specific query variants for non-English content.

    For German (de) a query like "Show S03 1080p" becomes:
        - "Show S03 German 1080p"
        - "Show S03 Deutsch 1080p"
        - "Show S03 GERMAN 1080p"

    Returns the original queries plus language-augmented ones (deduplicated).
    """
    cfg = _LANGUAGE_CONFIG.get(lang_code, {})
    keywords = cfg.get("keywords", [])
    season_word = cfg.get("season_word", "")

    extra: List[str] = []
    for q in base_queries:
        for kw in keywords[:2]:  # top 2 keywords to keep result count manageable
            extra.append(f"{q} {kw}")

    # If season_word differs from "Season", add a native-language variant
    if season_word and season_word.lower() != "season":
        # Replace "Season N" with the native equivalent if present
        for q in base_queries:
            native_q = q
            import re
            native_q = re.sub(
                r"\bSeason\s+(\d+)\b",
                lambda m: f"{season_word} {m.group(1)}",
                native_q,
                flags=re.IGNORECASE,
            )
            if native_q != q:
                extra.append(native_q)

    seen = set(base_queries)
    result = list(base_queries)
    for q in extra:
        if q not in seen:
            seen.add(q)
            result.append(q)
    return result


def _rank_with_language(
    results: List[Dict[str, Any]],
    lang_code: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Rank results, with an additional bonus for language-matching titles when
    a specific language is requested.
    """
    cfg = _LANGUAGE_CONFIG.get(lang_code or "", {})
    release_patterns = [p.lower() for p in cfg.get("release_patterns", [])]

    def _score(r: Dict[str, Any]) -> int:
        title_lower = r["title"].lower()
        # Pack bonus (inherited from TorrentSearchClient.rank)
        pack_bonus = 1000 if any(
            kw in title_lower for kw in ("complete", "season", " pack", "collection")
        ) else 0
        # Language match bonus — strongly prefer language-tagged releases
        lang_bonus = 2000 if lang_code and any(
            pat in title_lower for pat in release_patterns
        ) else 0
        return lang_bonus + pack_bonus + r.get("seeders", 0)

    return sorted(results, key=_score, reverse=True)


async def search_torrents(
    client: TorrentSearchClient,
    query: str,
    limit: int = 10,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Search for torrents across configured providers.

    Args:
        client: TorrentSearchClient instance
        query: Search query string
        limit: Maximum number of results (default 10)
        language: Optional language preference (e.g. "de", "german", "fr").
                  When set, language-specific keywords are appended to the query
                  and matching results are ranked higher.

    Returns:
        Dictionary with ranked results list and total count.
    """
    if not client.is_available:
        return _UNAVAILABLE

    lang_code = _resolve_language(language)
    queries = _build_language_queries([query], lang_code) if lang_code else [query]

    seen_ids: set = set()
    all_results = []
    for q in queries:
        results = await client.search(q, limit=limit)
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                all_results.append(r)

    ranked = _rank_with_language(all_results, lang_code)

    resp: Dict[str, Any] = {"results": ranked[:limit], "total": len(ranked), "query": query}
    if lang_code:
        resp["language"] = lang_code
        cfg = _LANGUAGE_CONFIG.get(lang_code, {})
        if cfg.get("indexer_notes"):
            resp["indexer_tip"] = cfg["indexer_notes"]
    return resp


async def get_torrent_magnet(
    client: TorrentSearchClient,
    torrent_id: str,
) -> Dict[str, Any]:
    """Resolve a torrent search result ID to its magnet link.

    Args:
        client: TorrentSearchClient instance
        torrent_id: ID string from a search_torrents result

    Returns:
        Dictionary with torrent_id and magnet URI.
    """
    if not client.is_available:
        return _UNAVAILABLE

    magnet = await client.get_magnet(torrent_id)
    if not magnet:
        return {"error": f"Could not retrieve magnet for id={torrent_id!r}"}
    return {"torrent_id": torrent_id, "magnet": magnet}


async def search_season(
    client: TorrentSearchClient,
    show_title: str,
    season: int,
    quality: str = "1080p",
    limit: int = 5,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Search for a complete season pack for a TV show.

    Runs optimised queries and deduplicates results. When a non-English language
    is specified, additional language-tagged queries are generated and results
    matching the language are ranked higher.

    Base queries:
        "{show} Season {N} complete {quality}"
        "{show} S{NN} {quality}"

    German (language="de") adds:
        "{show} Season {N} complete {quality} German"
        "{show} S{NN} {quality} Deutsch"
        "{show} Staffel {N} German"   ← native season word

    Args:
        client: TorrentSearchClient instance
        show_title: TV show name (e.g. "Ted Lasso")
        season: Season number
        quality: Preferred quality string (default "1080p")
        limit: Max results to return (default 5)
        language: Optional language code or name (e.g. "de", "german", "fr").
                  Supported: de, fr, es, it, ja (and English names thereof).

    Returns:
        Dictionary with ranked results. Includes "language" and "indexer_tip"
        keys when a language is specified.
    """
    if not client.is_available:
        return _UNAVAILABLE

    lang_code = _resolve_language(language)

    base_queries = [
        f"{show_title} Season {season} complete {quality}",
        f"{show_title} S{season:02d} {quality}",
    ]
    queries = _build_language_queries(base_queries, lang_code) if lang_code else base_queries

    seen_ids: set = set()
    all_results = []
    for q in queries:
        results = await client.search(q, limit=limit)
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                all_results.append(r)

    ranked = _rank_with_language(all_results, lang_code)

    resp: Dict[str, Any] = {
        "show": show_title,
        "season": season,
        "quality": quality,
        "results": ranked[:limit],
        "total": len(ranked),
    }
    if lang_code:
        resp["language"] = lang_code
        cfg = _LANGUAGE_CONFIG.get(lang_code, {})
        if cfg.get("indexer_notes"):
            resp["indexer_tip"] = cfg["indexer_notes"]
    return resp
