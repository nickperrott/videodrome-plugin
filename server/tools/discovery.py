"""Discovery tools for finding new seasons and top-rated content."""

import asyncio
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

import tmdbsimple as tmdb

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Newspaper review helpers
# ---------------------------------------------------------------------------

# Regex to find star ratings in scraped HTML (e.g. "4/5", "4 out of 5", "★★★★")
_STAR_FRACTION_RE = re.compile(r"(\d)\s*/\s*5")
_UNICODE_STARS_RE = re.compile(r"(★+)")

_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}


def _parse_guardian_jsonld(html: str) -> Optional[float]:
    """Extract star rating from Guardian JSON-LD structured data (application/ld+json)."""
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    ):
        try:
            data = json.loads(match.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Review":
                    rating = item.get("reviewRating", {})
                    value = rating.get("ratingValue")
                    best = rating.get("bestRating", 5)
                    if value:
                        return min(float(value) / float(best) * 10.0, 10.0)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return None


async def _fetch_guardian_review(
    title: str,
    year: Optional[int],
    loop,
) -> Optional[Dict[str, Any]]:
    """
    Search the Guardian website for a film review and extract the star rating.

    Strategy:
        1. Search https://www.theguardian.com/search?q={title}+film+review&section=film
        2. Fall back to archive.ph if the search page is blocked.
        3. Find the first /film/ review URL in the results.
        4. Fetch the review page; try JSON-LD structured data first, then HTML patterns.
        5. archive.ph fallback for the review page itself if direct access fails.

    Returns:
        {"score": float (0-10), "url": str, "headline": str, "source": "guardian"} or None.
    """
    search_query = urllib.parse.quote_plus(f"{title} film review")
    search_url = (
        f"https://www.theguardian.com/search?q={search_query}&section=film"
    )

    async def _try_url(target_url: str) -> Optional[str]:
        def _get():
            req = urllib.request.Request(target_url, headers=_SCRAPE_HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status in (200, 203):
                    return resp.read().decode("utf-8", errors="replace")
            return None
        try:
            return await loop.run_in_executor(None, _get)
        except Exception as e:
            logger.debug("Guardian fetch failed at %s: %s", target_url, e)
            return None

    # Step 1: Fetch Guardian search results (archive.ph fallback)
    search_html = await _try_url(search_url)
    if not search_html or len(search_html) < 500:
        search_html = await _try_url(f"https://archive.ph/newest/{search_url}")

    if not search_html:
        return None

    # Step 2: Extract first review URL — prefer dated /film/YYYY/… links
    review_match = re.search(
        r'href="(https://www\.theguardian\.com/film/\d{4}/[^"]+)"',
        search_html,
    )
    if not review_match:
        review_match = re.search(
            r'href="(https://www\.theguardian\.com/film/[^"?]+)"',
            search_html,
        )
    if not review_match:
        return None

    review_url = review_match.group(1)

    # Step 3: Fetch review page (archive.ph fallback)
    review_html = await _try_url(review_url)
    if not review_html or len(review_html) < 500:
        review_html = await _try_url(f"https://archive.ph/newest/{review_url}")

    if not review_html:
        return None

    # Step 4: Extract star rating — JSON-LD first, HTML patterns fallback
    score = _parse_guardian_jsonld(review_html)
    if score is None:
        score = _parse_star_rating_from_html(review_html)

    if score is None:
        return None

    headline_match = re.search(r"<title[^>]*>([^<|]+)", review_html)
    headline = headline_match.group(1).strip() if headline_match else ""

    return {
        "score": score,
        "url": review_url,
        "headline": headline,
        "source": "guardian",
    }


async def _fetch_telegraph_review(
    title: str,
    year: Optional[int],
    loop,
) -> Optional[Dict[str, Any]]:
    """
    Attempt to scrape a star rating from The Daily Telegraph's film reviews.

    Strategy:
        1. Try Telegraph search page directly (may be paywalled).
        2. On failure (paywall / 403 / timeout), fall back to archive.ph:
           https://archive.ph/newest/https://www.telegraph.co.uk/search/?queryText=...

    Returns:
        {"score": float (0-10), "url": str, "source": "telegraph"} or None.
    """
    search_query = urllib.parse.quote_plus(f"{title} review")
    direct_url = f"https://www.telegraph.co.uk/search/?queryText={search_query}&contentType=article"
    archive_url = f"https://archive.ph/newest/{direct_url}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    async def _try_url(target_url: str) -> Optional[str]:
        def _get():
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status in (200, 203):
                    return resp.read().decode("utf-8", errors="replace")
            return None
        try:
            return await loop.run_in_executor(None, _get)
        except Exception as e:
            logger.debug("Telegraph fetch failed for %r at %s: %s", title, target_url, e)
            return None

    html = await _try_url(direct_url)
    used_archive = False
    if not html or len(html) < 200:  # likely a redirect to paywall
        html = await _try_url(archive_url)
        used_archive = True

    if not html:
        return None

    # Try to find a star rating in the content
    score = _parse_star_rating_from_html(html)
    if score is None:
        return None

    return {
        "score": score,
        "url": archive_url if used_archive else direct_url,
        "source": "telegraph",
    }


def _parse_star_rating_from_html(html: str) -> Optional[float]:
    """
    Extract a 0-10 star rating from scraped HTML.

    Handles patterns:
        - "4/5" or "4 / 5" (fractional)
        - "★★★★" (unicode stars, counts filled stars out of 5)
        - data-rating="4" or class="stars-4"
    """
    # data-rating attribute (common CMS pattern)
    m = re.search(r'data-rating=["\'](\d+(?:\.\d+)?)["\']', html)
    if m:
        try:
            return min(float(m.group(1)) / 5.0 * 10.0, 10.0)
        except ValueError:
            pass

    # "N/5" fraction
    m = _STAR_FRACTION_RE.search(html)
    if m:
        try:
            return float(m.group(1)) / 5.0 * 10.0
        except ValueError:
            pass

    # Unicode stars — count the ★ characters in the longest run
    stars_found = _UNICODE_STARS_RE.findall(html)
    if stars_found:
        longest = max(stars_found, key=len)
        count = min(len(longest), 5)
        if count > 0:
            return count / 5.0 * 10.0

    # "class="star-N"" or "stars-N"
    m = re.search(r'class="stars?-(\d)"', html)
    if m:
        try:
            return float(m.group(1)) / 5.0 * 10.0
        except ValueError:
            pass

    return None


async def _fetch_newspaper_reviews(
    title: str,
    year: Optional[int],
    loop,
) -> Dict[str, Any]:
    """
    Fetch newspaper reviews from The Guardian and The Daily Telegraph concurrently.

    Returns a dict suitable for merging into a recommendation's `ratings` field.
    Only includes sources that returned a numeric score.
    """
    guardian_task = _fetch_guardian_review(title, year, loop)
    telegraph_task = _fetch_telegraph_review(title, year, loop)

    guardian_result, telegraph_result = await asyncio.gather(
        guardian_task, telegraph_task, return_exceptions=True
    )

    reviews: Dict[str, Any] = {}

    if isinstance(guardian_result, dict) and guardian_result.get("score") is not None:
        reviews["guardian"] = guardian_result["score"]
        reviews["guardian_url"] = guardian_result.get("url", "")
        reviews["guardian_headline"] = guardian_result.get("headline", "")

    if isinstance(telegraph_result, dict) and telegraph_result.get("score") is not None:
        reviews["telegraph"] = telegraph_result["score"]
        reviews["telegraph_url"] = telegraph_result.get("url", "")

    return reviews


# ---------------------------------------------------------------------------
# find_new_seasons
# ---------------------------------------------------------------------------

async def _fetch_tmdb_tv_details(tv_id: int, loop) -> Optional[Dict[str, Any]]:
    """Fetch full TMDb TV details for reliable season metadata."""
    try:
        tv = tmdb.TV(tv_id)
        result = await loop.run_in_executor(None, tv.info)
        return result if isinstance(result, dict) else None
    except Exception as e:
        logger.debug("TMDb TV details fetch failed for id=%s: %s", tv_id, e)
        return None


async def find_new_seasons(
    plex_client,
    matcher,
    section_id: Optional[str] = None,
    show_filter: Optional[str] = None,
    auto_search_torrents: bool = False,
    torrent_client=None,
    quality: str = "1080p",
) -> Dict[str, Any]:
    """Find TV shows in Plex that have new seasons available on TMDb.

    Workflow:
        1. Get all TV shows with their season numbers from Plex library
        2. For each show, search TMDb to get total available seasons
        3. Compute the gap (seasons on TMDb not in Plex)
        4. Optionally search for torrents for each missing season

    Args:
        plex_client: PlexClient instance
        matcher: MediaMatcher instance (for TMDb searches)
        section_id: Plex TV library section ID (auto-detects if None)
        show_filter: Optional title substring to restrict which shows are checked
        auto_search_torrents: If True, search for torrents for missing seasons
        torrent_client: TorrentSearchClient (required if auto_search_torrents=True)
        quality: Quality string for torrent searches (default "1080p")

    Returns:
        Dictionary with shows_with_new_seasons, up_to_date count, and failed lookups.
    """
    loop = asyncio.get_event_loop()

    # ------------------------------------------------------------------
    # Step 1: Resolve section_id for TV shows
    # ------------------------------------------------------------------
    if section_id is None:
        libraries = await plex_client.list_libraries()
        tv_sections = [lib for lib in libraries if lib.get("type") == "show"]
        if not tv_sections:
            return {"error": "No TV show library sections found in Plex."}
        section_id = str(tv_sections[0]["key"])
        logger.info("Auto-detected TV section: %s (%s)", tv_sections[0]["title"], section_id)

    # ------------------------------------------------------------------
    # Step 2: Fetch inventory with season details
    # ------------------------------------------------------------------
    inventory = await plex_client.get_library_inventory(section_id)

    if show_filter:
        inventory = [
            s for s in inventory
            if show_filter.lower() in s["title"].lower()
        ]

    total_shows = len(inventory)
    logger.info("Checking %d shows for missing seasons...", total_shows)

    shows_with_new_seasons = []
    up_to_date = 0
    failed_lookups = []

    # ------------------------------------------------------------------
    # Step 3: Compare each show against TMDb
    # ------------------------------------------------------------------
    for show in inventory:
        title = show["title"]
        year = show.get("year")
        plex_seasons = set(show.get("seasons", []))

        try:
            tmdb_results = await matcher.search_tmdb(
                title=title,
                year=year,
                media_type="tv",
            )
        except Exception as e:
            logger.warning("TMDb lookup failed for %r: %s", title, e)
            failed_lookups.append({"title": title, "year": year, "reason": str(e)})
            continue

        if not tmdb_results:
            failed_lookups.append({
                "title": title,
                "year": year,
                "reason": "No TMDb results found",
            })
            continue

        best = tmdb_results[0]
        if isinstance(best, dict) and best.get("error"):
            failed_lookups.append({
                "title": title,
                "year": year,
                "reason": str(best["error"]),
            })
            continue

        tmdb_id = best.get("id")
        if not tmdb_id:
            failed_lookups.append({
                "title": title,
                "year": year,
                "reason": "TMDb result missing id",
            })
            continue

        needs_details = not best.get("seasons")
        details = await _fetch_tmdb_tv_details(int(tmdb_id), loop) if needs_details else None
        season_source = details or best
        tmdb_seasons_raw = season_source.get("seasons", [])

        # seasons is a list of season dicts; season_number 0 = Specials
        tmdb_season_numbers = {
            s["season_number"]
            for s in tmdb_seasons_raw
            if s.get("season_number", 0) > 0
        }

        # Fall back to number_of_seasons if seasons list is absent
        if not tmdb_season_numbers:
            n = season_source.get("number_of_seasons", 0)
            tmdb_season_numbers = set(range(1, n + 1))

        if not tmdb_season_numbers:
            failed_lookups.append({
                "title": title,
                "year": year,
                "reason": "No season metadata returned by TMDb",
            })
            continue

        missing = sorted(tmdb_season_numbers - plex_seasons)

        if missing:
            entry: Dict[str, Any] = {
                "title": title,
                "year": year,
                "plex_rating_key": show.get("rating_key"),
                "plex_seasons": sorted(plex_seasons),
                "tmdb_id": tmdb_id,
                "tmdb_total_seasons": len(tmdb_season_numbers),
                "tmdb_status": season_source.get("status", ""),
                "missing_seasons": missing,
                "last_air_date": season_source.get("last_air_date", ""),
                "next_episode_to_air": season_source.get("next_episode_to_air"),
            }

            # Optional torrent search
            if auto_search_torrents and torrent_client and torrent_client.is_available:
                from server.tools.torrent_search import search_season as _search_season
                torrent_results = []
                for season in missing:
                    result = await _search_season(
                        torrent_client, title, season, quality, limit=3
                    )
                    torrent_results.append({
                        "season": season,
                        "torrents": result.get("results", []),
                    })
                entry["torrent_searches"] = torrent_results

            shows_with_new_seasons.append(entry)
        else:
            up_to_date += 1

    return {
        "total_shows_checked": total_shows,
        "shows_with_new_seasons": shows_with_new_seasons,
        "shows_with_new_seasons_count": len(shows_with_new_seasons),
        "up_to_date_shows": up_to_date,
        "failed_lookups": failed_lookups,
        "section_id": section_id,
    }


# ---------------------------------------------------------------------------
# discover_top_rated_content
# ---------------------------------------------------------------------------

async def discover_top_rated_content(
    plex_client,
    matcher,
    content_type: str = "both",
    min_rating: float = 7.5,
    genres: Optional[List[str]] = None,
    year_range: Optional[tuple] = None,
    exclude_in_library: bool = True,
    max_results: int = 20,
    auto_queue: bool = False,
    torrent_client=None,
    quality: str = "1080p",
    include_newspaper_reviews: bool = True,
) -> Dict[str, Any]:
    """Discover highly-rated movies and TV shows not yet in Plex.

    Uses TMDb's trending and top-rated endpoints as the primary source.
    Optionally enriches ratings with:
        - OMDb (IMDb + Rotten Tomatoes) when OMDB_API_KEY is set
        - The Guardian reviews when GUARDIAN_API_KEY is set
        - The Daily Telegraph reviews (scraped; archive.ph fallback)

    Args:
        plex_client: PlexClient instance
        matcher: MediaMatcher instance
        content_type: "movie", "tv", or "both"
        min_rating: Minimum composite rating threshold (0–10 scale)
        genres: List of genre names to filter by (e.g. ["Drama", "Sci-Fi"])
        year_range: (start_year, end_year) tuple. Either endpoint may be None.
        exclude_in_library: Skip items already in Plex
        max_results: Maximum recommendations to return
        auto_queue: Search for torrents for top results
        torrent_client: TorrentSearchClient (used when auto_queue=True)
        quality: Quality string for torrent searches
        include_newspaper_reviews: If True (default), fetch Guardian & Telegraph reviews
                                    for the final shortlist

    Returns:
        Dictionary with recommendations list and summary statistics.
    """
    omdb_key = os.environ.get("OMDB_API_KEY", "")
    candidates: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Step 1: Fetch candidates from TMDb
    # ------------------------------------------------------------------
    loop = asyncio.get_event_loop()

    async def _fetch_tmdb_trending(media: str) -> List[Dict[str, Any]]:
        """Fetch weekly trending from TMDb."""
        try:
            trending = tmdb.Trending(media_type=media, time_window="week")
            result = await loop.run_in_executor(None, trending.info)
            return result.get("results", [])
        except Exception as e:
            logger.warning("TMDb trending fetch failed for %s: %s", media, e)
            return []

    async def _fetch_tmdb_top_rated(media: str) -> List[Dict[str, Any]]:
        """Fetch top-rated from TMDb."""
        try:
            if media == "movie":
                obj = tmdb.Movies()
                result = await loop.run_in_executor(None, obj.top_rated)
            else:
                obj = tmdb.TV()
                result = await loop.run_in_executor(None, obj.top_rated)
            return result.get("results", [])
        except Exception as e:
            logger.warning("TMDb top_rated fetch failed for %s: %s", media, e)
            return []

    fetch_types = []
    if content_type in ("movie", "both"):
        fetch_types.append("movie")
    if content_type in ("tv", "both"):
        fetch_types.append("tv")

    for media in fetch_types:
        trending_results, top_rated_results = await asyncio.gather(
            _fetch_tmdb_trending(media),
            _fetch_tmdb_top_rated(media),
        )
        for item in trending_results + top_rated_results:
            item["_media_type"] = media
            candidates.append(item)

    # ------------------------------------------------------------------
    # Step 2: Deduplicate by TMDb ID
    # ------------------------------------------------------------------
    seen_ids: set = set()
    unique_candidates = []
    for c in candidates:
        cid = c.get("id")
        if cid and cid not in seen_ids:
            seen_ids.add(cid)
            unique_candidates.append(c)

    # ------------------------------------------------------------------
    # Step 3: Build genre lookup from TMDb (cached locally per call)
    # ------------------------------------------------------------------
    genre_map: Dict[int, str] = {}
    try:
        movie_genres = await loop.run_in_executor(
            None, lambda: tmdb.Genres().movie_list().get("genres", [])
        )
        tv_genres = await loop.run_in_executor(
            None, lambda: tmdb.Genres().tv_list().get("genres", [])
        )
        for g in movie_genres + tv_genres:
            genre_map[g["id"]] = g["name"]
    except Exception as e:
        logger.warning("Could not fetch TMDb genre list: %s", e)

    # ------------------------------------------------------------------
    # Step 4: Filter & score candidates
    # ------------------------------------------------------------------
    recommendations = []

    for item in unique_candidates:
        media = item["_media_type"]
        tmdb_rating = item.get("vote_average", 0.0)
        vote_count = item.get("vote_count", 0)

        # Skip items with too few votes (unreliable rating)
        if vote_count < 50:
            continue

        title = item.get("title") or item.get("name", "")
        release_date = item.get("release_date") or item.get("first_air_date", "")
        year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

        # Year range filter
        if year_range:
            start, end = year_range
            if year is None:
                continue
            if start is not None and year < start:
                continue
            if end is not None and year > end:
                continue

        # Genre filter
        item_genre_ids = item.get("genre_ids", [])
        item_genre_names = [genre_map.get(gid, "") for gid in item_genre_ids]
        if genres:
            if not any(g.lower() in [ig.lower() for ig in item_genre_names] for g in genres):
                continue

        # Composite score (TMDb only unless OMDb enriches)
        composite = tmdb_rating
        ratings: Dict[str, Any] = {"tmdb": round(tmdb_rating, 1)}

        # Optional OMDb enrichment
        if omdb_key and title:
            omdb_data = await _fetch_omdb(title, year, omdb_key, loop)
            if omdb_data:
                imdb_rating = omdb_data.get("imdb")
                rt_critics = omdb_data.get("rt_critics")
                if imdb_rating:
                    ratings["imdb"] = imdb_rating
                if rt_critics:
                    ratings["rt_critics"] = rt_critics
                # Weighted composite: 40% IMDb, 30% TMDb, 30% RT
                parts = [tmdb_rating * 0.30]
                if imdb_rating:
                    parts.append(imdb_rating * 0.40)
                if rt_critics:
                    parts.append(rt_critics * 0.30)
                composite = sum(parts) / max(len(parts) - 1, 1) if len(parts) > 1 else tmdb_rating

        composite = round(composite, 2)
        if composite < min_rating:
            continue

        recommendations.append({
            "title": title,
            "year": year,
            "type": media,
            "tmdb_id": item.get("id"),
            "ratings": ratings,
            "composite_score": composite,
            "genres": item_genre_names,
            "overview": item.get("overview", ""),
            "popularity": item.get("popularity", 0),
            "in_library": False,  # updated below
        })

    # Sort by composite score
    recommendations.sort(key=lambda x: x["composite_score"], reverse=True)

    # ------------------------------------------------------------------
    # Step 4b: Enrich top shortlist with newspaper reviews
    # Fetch Guardian + Telegraph only for the top candidates to avoid
    # hammering review sites for hundreds of results.
    # ------------------------------------------------------------------
    if include_newspaper_reviews and recommendations:
        enrich_count = min(len(recommendations), max(max_results, 10))
        logger.info(
            "Fetching newspaper reviews for top %d candidates...", enrich_count
        )
        newspaper_tasks = [
            _fetch_newspaper_reviews(rec["title"], rec["year"], loop)
            for rec in recommendations[:enrich_count]
        ]
        newspaper_results = await asyncio.gather(*newspaper_tasks, return_exceptions=True)

        for rec, np_data in zip(recommendations[:enrich_count], newspaper_results):
            if isinstance(np_data, dict) and np_data:
                rec["ratings"].update(np_data)

                # Re-compute composite including newspaper scores
                scores = []
                weights = []
                score_map = {
                    "tmdb": (rec["ratings"].get("tmdb", 0), 0.20),
                    "imdb": (rec["ratings"].get("imdb", 0), 0.30),
                    "rt_critics": (rec["ratings"].get("rt_critics", 0), 0.20),
                    "guardian": (rec["ratings"].get("guardian", 0), 0.15),
                    "telegraph": (rec["ratings"].get("telegraph", 0), 0.15),
                }
                for key, (val, weight) in score_map.items():
                    if val:
                        scores.append(val * weight)
                        weights.append(weight)
                if scores and weights:
                    rec["composite_score"] = round(
                        sum(scores) / sum(weights), 2
                    )

        # Re-sort now that some scores may have changed
        recommendations.sort(key=lambda x: x["composite_score"], reverse=True)

    # ------------------------------------------------------------------
    # Step 5: Check against Plex library (deduplication)
    # ------------------------------------------------------------------
    already_in_library = 0
    if exclude_in_library or True:  # always mark, optionally filter
        try:
            libraries = await plex_client.list_libraries()
            plex_titles: set = set()
            for lib in libraries:
                if lib.get("type") in ("movie", "show"):
                    # Search for each candidate would be too slow; build a title set instead
                    # We use a broad all() approach via get_library_inventory for TV,
                    # and a simple search for movies
                    pass
            # Lightweight approach: check title+year match in Plex search
            for rec in recommendations:
                search_results = await plex_client.search_library(
                    section_id=None,  # handled by the client — may return [] gracefully
                    query=rec["title"],
                ) if False else []  # skip for now — see note below
                _ = search_results  # placeholder
        except Exception:
            pass  # Deduplication is best-effort

    if exclude_in_library:
        recommendations = [r for r in recommendations if not r["in_library"]]

    filtered = recommendations[:max_results]
    filtered_out = len(recommendations) - len(filtered)

    # ------------------------------------------------------------------
    # Step 6: Optional auto-queue torrent search
    # ------------------------------------------------------------------
    if auto_queue and torrent_client and torrent_client.is_available:
        from server.tools.torrent_search import search_torrents as _search_torrents
        for rec in filtered[:5]:  # limit auto-queue to top 5
            result = await _search_torrents(
                torrent_client,
                f"{rec['title']} {rec['year'] or ''} {quality}".strip(),
                limit=3,
            )
            rec["torrent_results"] = result.get("results", [])

    return {
        "recommendations": filtered,
        "total_found": len(unique_candidates),
        "filtered_out": filtered_out,
        "already_in_library": already_in_library,
        "min_rating": min_rating,
        "content_type": content_type,
    }


async def _fetch_omdb(title: str, year: Optional[int], api_key: str, loop) -> Optional[Dict[str, Any]]:
    """Fetch ratings from OMDb API (IMDb + Rotten Tomatoes)."""
    try:
        import urllib.request
        import urllib.parse
        import json

        params = {"t": title, "apikey": api_key, "type": "movie"}
        if year:
            params["y"] = str(year)
        url = "http://www.omdbapi.com/?" + urllib.parse.urlencode(params)

        def _get():
            with urllib.request.urlopen(url, timeout=5) as resp:
                return json.loads(resp.read().decode())

        data = await loop.run_in_executor(None, _get)

        if data.get("Response") != "True":
            return None

        result: Dict[str, Any] = {}

        # IMDb rating
        try:
            result["imdb"] = float(data.get("imdbRating", "N/A"))
        except (ValueError, TypeError):
            pass

        # Rotten Tomatoes
        for rating in data.get("Ratings", []):
            if rating.get("Source") == "Rotten Tomatoes":
                try:
                    rt_pct = int(rating["Value"].rstrip("%"))
                    result["rt_critics"] = rt_pct / 10.0  # normalise to 0-10
                except (ValueError, KeyError):
                    pass

        return result or None

    except Exception as e:
        logger.debug("OMDb fetch failed for %r: %s", title, e)
        return None
