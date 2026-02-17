"""Media matcher using guessit + TMDb pipeline."""

import re
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from difflib import SequenceMatcher

import guessit
import tmdbsimple as tmdb

from server.tmdb_cache import TMDbCache

logger = logging.getLogger(__name__)


class MediaMatcher:
    """Match media files using guessit parsing and TMDb search."""

    def __init__(
        self,
        tmdb_api_key: str,
        cache: Optional[TMDbCache] = None,
        media_root: str = "/data/media"
    ):
        """Initialize MediaMatcher.

        Args:
            tmdb_api_key: TMDb API key
            cache: Optional TMDbCache instance
            media_root: Root path for Plex media libraries
        """
        self.tmdb_api_key = tmdb_api_key
        self.cache = cache
        self.media_root = Path(media_root)
        tmdb.API_KEY = tmdb_api_key

    async def parse_filename(self, filename: str) -> Dict[str, Any]:
        """Parse filename using guessit.

        Args:
            filename: Filename to parse

        Returns:
            Parsed metadata dictionary
        """
        # Run guessit in executor since it's CPU-bound
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, guessit.guessit, filename)
        return dict(result)

    async def search_tmdb(
        self,
        title: str,
        year: Optional[int] = None,
        media_type: str = "movie",
        max_retries: int = 3,
    ) -> List[Dict[str, Any]]:
        """Search TMDb for media.

        Args:
            title: Media title
            year: Release year (optional)
            media_type: "movie" or "tv"
            max_retries: Number of retry attempts on transient errors (default 3)

        Returns:
            List of TMDb results.

        Raises:
            RuntimeError: If TMDb search fails after retries.
        """
        # Check cache first
        if self.cache:
            cached = await self.cache.get(title, year, media_type)
            if cached:
                return cached if isinstance(cached, list) else [cached]

        loop = asyncio.get_event_loop()
        search = tmdb.Search()

        # Strip None year to avoid passing year=None to the API which some
        # versions of tmdbsimple serialise as the string "None".
        safe_year = year if year else None

        def do_search() -> Dict[str, Any]:
            if media_type == "tv":
                return search.tv(query=title, first_air_date_year=safe_year)
            else:
                return search.movie(query=title, year=safe_year)

        last_error: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                result = await loop.run_in_executor(None, do_search)
                break
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    wait = 2 ** attempt  # exponential back-off: 2s, 4s
                    logger.warning(
                        "TMDb search attempt %d/%d failed for %r (%s): %s — retrying in %ds",
                        attempt, max_retries, title, media_type, exc, wait,
                    )
                    await asyncio.sleep(wait)
        else:
            logger.error(
                "TMDb search failed after %d attempts for %r (%s): %s",
                max_retries, title, media_type, last_error,
            )
            raise RuntimeError(
                f"TMDb search failed after {max_retries} attempts for {title!r} ({media_type})"
            ) from last_error

        results = result.get("results", [])

        # Add media_type to each result for downstream consumers
        for r in results:
            r["media_type"] = media_type

        # Store in cache
        if self.cache and results:
            await self.cache.store(title, year, media_type, results)

        return results

    async def calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles.

        Args:
            title1: First title
            title2: Second title

        Returns:
            Similarity score (0.0 to 1.0)
        """
        title1_clean = title1.lower().strip()
        title2_clean = title2.lower().strip()
        return SequenceMatcher(None, title1_clean, title2_clean).ratio()

    async def calculate_confidence(
        self,
        parsed: Dict[str, Any],
        tmdb_result: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for a match.

        Weights:
        - Title similarity: 40%
        - Year match: 30%
        - Popularity: 15%
        - Type match: 15%

        Args:
            parsed: Parsed metadata from guessit
            tmdb_result: TMDb result

        Returns:
            Confidence score (0.0 to 1.0)
        """
        score = 0.0

        # Title similarity (40%)
        parsed_title = parsed.get("title", "")
        tmdb_title = tmdb_result.get("title") or tmdb_result.get("name", "")
        title_sim = await self.calculate_title_similarity(parsed_title, tmdb_title)
        score += title_sim * 0.40

        # Year match (30%)
        if "year" in parsed and parsed["year"]:
            parsed_year = parsed["year"]
            tmdb_date = tmdb_result.get("release_date") or tmdb_result.get("first_air_date", "")
            if tmdb_date:
                tmdb_year = int(tmdb_date[:4])
                if parsed_year == tmdb_year:
                    score += 0.30
                elif abs(parsed_year - tmdb_year) == 1:
                    score += 0.20  # Close year
                elif abs(parsed_year - tmdb_year) == 2:
                    score += 0.10  # Very close year
        else:
            # No year in parsed data, give partial credit
            score += 0.15

        # Popularity (15%) - normalize to 0-1 range
        popularity = tmdb_result.get("popularity", 0)
        # Use log scale for popularity, capping at 100
        popularity_score = min(popularity / 100.0, 1.0)
        score += popularity_score * 0.15

        # Type match (15%)
        parsed_type = parsed.get("type", "")
        tmdb_type = tmdb_result.get("media_type", "")

        if (parsed_type == "movie" and tmdb_type == "movie") or \
           (parsed_type == "episode" and tmdb_type == "tv"):
            score += 0.15
        elif parsed_type in ("movie", "episode"):  # Parsed type valid but mismatch
            score += 0.05

        return min(score, 1.0)

    async def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem safety.

        Args:
            filename: Filename to sanitize

        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        # Replace multiple spaces with single space
        filename = re.sub(r'\s+', ' ', filename)
        return filename.strip()

    async def get_episode_title(
        self,
        tv_id: int,
        season: int,
        episode: int
    ) -> str:
        """Get episode title from TMDb.

        Args:
            tv_id: TMDb TV show ID
            season: Season number
            episode: Episode number

        Returns:
            Episode title or generic fallback
        """
        try:
            loop = asyncio.get_event_loop()
            tv = tmdb.TV(tv_id)
            ep = tv.season(season).episode(episode)
            ep_info = await loop.run_in_executor(None, ep.info)
            return ep_info.get("name", f"Episode {episode}")
        except Exception:
            return f"Episode {episode}"

    async def construct_plex_path(
        self,
        parsed: Dict[str, Any],
        tmdb_result: Dict[str, Any],
        original_filename: str
    ) -> str:
        """Construct Plex-compatible path.

        Movie format:
            /Movies/Movie Name (Year) {tmdb-ID}/Movie Name (Year) {tmdb-ID}.ext

        TV format:
            /TV Shows/Show Name (Year)/Season 01/Show Name (Year) - s01e01 - Episode Title.ext

        Args:
            parsed: Parsed metadata from guessit
            tmdb_result: TMDb result
            original_filename: Original filename for extension

        Returns:
            Plex-compatible path
        """
        # Get extension
        ext = Path(original_filename).suffix

        media_type = parsed.get("type", "movie")
        tmdb_id = tmdb_result["id"]

        if media_type == "episode":
            # TV Show path
            show_name = tmdb_result.get("name", parsed["title"])
            show_name = await self.sanitize_filename(show_name)

            # Get year from first_air_date
            first_air = tmdb_result.get("first_air_date", "")
            year = first_air[:4] if first_air else parsed.get("year", "")

            season = parsed.get("season", 1)
            episode = parsed.get("episode", 1)

            # Get episode title
            episode_title = await self.get_episode_title(tmdb_id, season, episode)
            episode_title = await self.sanitize_filename(episode_title)

            season_str = f"Season {season:02d}"
            episode_str = f"s{season:02d}e{episode:02d}"

            if year:
                show_dir = f"{show_name} ({year})"
                filename = f"{show_name} ({year}) - {episode_str} - {episode_title}{ext}"
            else:
                show_dir = show_name
                filename = f"{show_name} - {episode_str} - {episode_title}{ext}"

            return str(
                self.media_root / "TV Shows" / show_dir / season_str / filename
            )
        else:
            # Movie path
            movie_name = tmdb_result.get("title", parsed["title"])
            movie_name = await self.sanitize_filename(movie_name)

            # Get year from release_date
            release_date = tmdb_result.get("release_date", "")
            year = release_date[:4] if release_date else parsed.get("year", "")

            if year:
                movie_dir = f"{movie_name} ({year}) {{tmdb-{tmdb_id}}}"
                filename = f"{movie_name} ({year}) {{tmdb-{tmdb_id}}}{ext}"
            else:
                movie_dir = f"{movie_name} {{tmdb-{tmdb_id}}}"
                filename = f"{movie_name} {{tmdb-{tmdb_id}}}{ext}"

            return str(
                self.media_root / "Movies" / movie_dir / filename
            )

    async def match_media(self, filename: str) -> Optional[Dict[str, Any]]:
        """Full matching pipeline for a media file.

        Args:
            filename: Filename to match

        Returns:
            Match result with parsed data, TMDb result, confidence, and Plex path,
            or None if no match found
        """
        # Parse filename
        parsed = await self.parse_filename(filename)

        if not parsed.get("title"):
            return None

        # Determine media type
        media_type = "tv" if parsed.get("type") == "episode" else "movie"

        # Search TMDb
        try:
            results = await self.search_tmdb(
                title=parsed["title"],
                year=parsed.get("year"),
                media_type=media_type
            )
        except Exception as exc:
            logger.warning("TMDb lookup failed while matching %r: %s", filename, exc)
            return None

        if not results:
            return None

        # Use first result and calculate confidence
        best_result = results[0]
        confidence = await self.calculate_confidence(parsed, best_result)

        # Construct Plex path
        plex_path = await self.construct_plex_path(parsed, best_result, filename)

        return {
            "parsed": parsed,
            "tmdb_id": best_result["id"],
            "tmdb_result": best_result,
            "confidence": confidence,
            "plex_path": plex_path
        }

    async def batch_match(self, filenames: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Match multiple files in batch.

        Args:
            filenames: List of filenames to match

        Returns:
            List of match results (None for failed matches)
        """
        tasks = [self.match_media(filename) for filename in filenames]
        return await asyncio.gather(*tasks, return_exceptions=False)
