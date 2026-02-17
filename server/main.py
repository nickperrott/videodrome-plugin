"""Videodrome MCP Server - Main entry point."""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from mcp.server import FastMCP

from server.client import create_plex_client
from server.tmdb_cache import TMDbCache
from server.matcher import MediaMatcher
from server.files import FileManager
from server.history import IngestHistory
from server.watcher import IngestWatcher
from server.transmission import TransmissionClient
from server.torrent_search import TorrentSearchClient
from server.tools import library, system, media, ingest, transmission
from server.tools import torrent_search as torrent_search_tools
from server.tools import nas as nas_tools
from server.tools import discovery as discovery_tools
from server.safety import validate_operation, get_safety_metadata, TOOL_SAFETY_MAP


def load_config():
    """Load configuration from ~/.config/videodrome/.env or current directory."""
    # Try config directory first
    config_dir = Path.home() / ".config" / "videodrome"
    config_file = config_dir / ".env"

    if config_file.exists():
        env_path = config_file
    else:
        # Fallback to current directory
        env_path = Path.cwd() / ".env"

    if env_path.exists():
        # Load environment variables from file
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, _, value = line.partition('=')
                    if key and value:
                        os.environ.setdefault(key.strip(), value.strip())
        return env_path
    return None


def get_env_with_fallback(new_key: str, old_key: str, required: bool = True) -> Optional[str]:
    """Get environment variable with fallback to old name and deprecation warning."""
    value = os.getenv(new_key)
    if value:
        return value

    # Try old name
    old_value = os.getenv(old_key)
    if old_value:
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Environment variable '{old_key}' is deprecated. "
            f"Please update to '{new_key}' in your configuration."
        )
        return old_value

    if required:
        raise ValueError(f"Missing required environment variable: {new_key} (or legacy {old_key})")

    return None


# Load configuration before anything else
config_path = load_config()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if config_path:
    logger.info(f"Loaded configuration from: {config_path}")
else:
    logger.warning("No .env file found. Using environment variables only.")


# Global instances (initialized in lifespan)
plex_client = None
tmdb_cache = None
matcher = None
file_manager = None
history = None
watcher: Optional[IngestWatcher] = None
transmission_client: Optional[TransmissionClient] = None
torrent_search_client: Optional[TorrentSearchClient] = None


@asynccontextmanager
async def lifespan(mcp: FastMCP):
    """Lifespan context manager for startup and shutdown."""
    global plex_client, tmdb_cache, matcher, file_manager, history, watcher, transmission_client, torrent_search_client

    logger.info("Starting Videodrome MCP Server...")

    # Load environment variables with fallback support
    plex_url = get_env_with_fallback("VIDEODROME_PLEX_URL", "PLEX_URL")
    plex_token = get_env_with_fallback("VIDEODROME_PLEX_TOKEN", "PLEX_TOKEN")
    tmdb_api_key = get_env_with_fallback("VIDEODROME_TMDB_API_KEY", "TMDB_API_KEY")
    media_root = get_env_with_fallback("VIDEODROME_MEDIA_ROOT", "PLEX_MEDIA_ROOT")
    ingest_dir = get_env_with_fallback("VIDEODROME_INGEST_DIR", "PLEX_INGEST_DIR", required=False)

    # Validate required env vars
    if not all([plex_url, plex_token, tmdb_api_key, media_root]):
        raise ValueError(
            "Missing required environment variables. "
            "Please set PLEX_URL, PLEX_TOKEN, TMDB_API_KEY, and PLEX_MEDIA_ROOT."
        )

    # Initialize Plex client
    logger.info(f"Connecting to Plex server at {plex_url}...")
    plex_client = create_plex_client(plex_url, plex_token)

    # Initialize TMDb cache
    cache_dir = Path.home() / ".cache" / "videodrome"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_db_path = cache_dir / "tmdb_cache.db"

    logger.info("Initializing TMDb cache...")
    tmdb_cache = TMDbCache(db_path=cache_db_path)
    await tmdb_cache.initialize()

    # Initialize MediaMatcher
    logger.info("Initializing MediaMatcher...")
    matcher = MediaMatcher(
        tmdb_api_key=tmdb_api_key,
        cache=tmdb_cache,
        media_root=media_root
    )

    # Initialize FileManager
    if ingest_dir:
        logger.info("Initializing FileManager...")
        file_manager = FileManager(
            media_root=media_root,
            ingest_dir=ingest_dir
        )

        # Initialize IngestHistory
        history_db_path = cache_dir / "ingest_history.db"
        logger.info("Initializing IngestHistory...")
        history = IngestHistory(db_path=history_db_path)
        await history.initialize()

        # Initialize Transmission client (optional)
        transmission_url = get_env_with_fallback("TRANSMISSION_URL", "TRANSMISSION_URL", required=False)
        if transmission_url:
            logger.info("Initializing Transmission client...")
            transmission_client = TransmissionClient(
                url=transmission_url,
                username=os.getenv("TRANSMISSION_USER"),
                password=os.getenv("TRANSMISSION_PASSWORD")
            )

            # Attempt to connect
            if transmission_client.connect():
                logger.info("Transmission client connected successfully")
            else:
                logger.warning("Failed to connect to Transmission. Torrent features will be unavailable.")
                transmission_client = None
        else:
            logger.info("TRANSMISSION_URL not set - torrent functionality disabled")

        # Initialize IngestWatcher
        auto_ingest = (get_env_with_fallback("VIDEODROME_AUTO_INGEST", "PLEX_AUTO_INGEST", required=False) or "false").lower() == "true"
        confidence_threshold = float(get_env_with_fallback("VIDEODROME_CONFIDENCE_THRESHOLD", "PLEX_CONFIDENCE_THRESHOLD", required=False) or "0.85")
        watcher_auto_start = (get_env_with_fallback("VIDEODROME_WATCHER_AUTO_START", "PLEX_WATCHER_AUTO_START", required=False) or "false").lower() == "true"

        logger.info("Initializing IngestWatcher...")
        watcher = IngestWatcher(
            ingest_dir=Path(ingest_dir),
            matcher=matcher,
            file_manager=file_manager,
            history=history,
            auto_ingest=auto_ingest,
            confidence_threshold=confidence_threshold,
            transmission_client=transmission_client
        )

        # Auto-start watcher if configured
        if watcher_auto_start:
            logger.info("Auto-starting watcher...")
            await watcher.start()
    else:
        logger.info("PLEX_INGEST_DIR not set - watcher functionality disabled")

    # Initialize TorrentSearchClient (gracefully no-ops if library not installed)
    providers_env = os.getenv("TORRENT_SEARCH_PROVIDERS", "thepiratebay")
    providers = [p.strip() for p in providers_env.split(",") if p.strip()]
    logger.info("Initializing TorrentSearchClient (providers: %s)...", providers)
    torrent_search_client = TorrentSearchClient(providers=providers)
    if torrent_search_client.connect():
        logger.info("Torrent search ready.")
    else:
        logger.info("Torrent search unavailable — install torrent-search-mcp to enable.")

    logger.info("Videodrome MCP Server started successfully!")

    # Yield control to FastMCP
    yield

    # Shutdown
    logger.info("Shutting down Videodrome MCP Server...")

    # Stop watcher
    if watcher and watcher.is_running:
        logger.info("Stopping watcher...")
        await watcher.stop()

    # Close database connections
    if history:
        await history.close()

    if tmdb_cache:
        await tmdb_cache.close()

    logger.info("Videodrome MCP Server shutdown complete.")


# Create FastMCP instance
mcp = FastMCP(
    "Videodrome",
    lifespan=lifespan
)


# =============================================================================
# Library Tools
# =============================================================================

@mcp.tool()
async def list_libraries() -> list[dict]:
    """List all Plex library sections."""
    return await library.list_libraries(plex_client)


@mcp.tool()
async def scan_library(section_id: str) -> dict:
    """Trigger a library scan.

    Args:
        section_id: Library section ID to scan
    """
    return await library.scan_library(plex_client, section_id)


@mcp.tool()
async def search_library(section_id: str, query: str) -> list[dict]:
    """Search for media in a library section.

    Args:
        section_id: Library section ID to search
        query: Search query string
    """
    return await library.search_library(plex_client, section_id, query)


@mcp.tool()
async def list_recent(section_id: str, limit: int = 20) -> list[dict]:
    """List recently added items in a library section.

    Args:
        section_id: Library section ID
        limit: Maximum number of items to return (default: 20)
    """
    return await library.list_recent(plex_client, section_id, limit)


# =============================================================================
# System Tools
# =============================================================================

@mcp.tool()
async def get_server_info() -> dict:
    """Get Plex server information."""
    return await system.get_server_info(plex_client)


# =============================================================================
# Media Tools
# =============================================================================

@mcp.tool()
async def parse_filename(filename: str) -> dict:
    """Parse a media filename using guessit.

    Args:
        filename: Filename to parse
    """
    return await media.parse_filename(filename)


@mcp.tool()
async def search_tmdb(title: str, year: Optional[int] = None, media_type: str = "movie") -> list[dict]:
    """Search TMDb for media.

    Args:
        title: Media title to search for
        year: Release year (optional)
        media_type: Type of media - "movie" or "tv" (default: "movie")
    """
    return await media.search_tmdb(title, year, media_type)


@mcp.tool()
async def preview_rename(filename: str) -> dict:
    """Preview Plex-compatible rename for a file.

    Args:
        filename: Filename to preview
    """
    return await media.preview_rename(filename)


@mcp.tool()
async def batch_identify(directory: str) -> list[dict]:
    """Identify all media files in a directory.

    Args:
        directory: Directory path to scan
    """
    return await media.batch_identify(directory)


# =============================================================================
# Ingest Tools (only if file_manager is initialized)
# =============================================================================

@mcp.tool()
async def list_ingest_files() -> list[dict]:
    """List files in the ingest directory."""
    if not file_manager:
        return {"error": "Ingest functionality not configured (PLEX_INGEST_DIR not set)"}
    return await ingest.list_ingest_files(file_manager)


@mcp.tool()
async def ingest_file(source: str, destination: str) -> dict:
    """Ingest a file from source to destination.

    Args:
        source: Source file path
        destination: Destination file path
    """
    if not file_manager or not history:
        return {"error": "Ingest functionality not configured"}
    return await ingest.ingest_file(file_manager, history, source, destination)


@mcp.tool()
async def get_ingest_history(
    status: Optional[str] = None,
    tmdb_id: Optional[int] = None,
    media_type: Optional[str] = None,
    limit: int = 50
) -> list[dict]:
    """Query ingest history.

    Args:
        status: Filter by status (SUCCESS/FAILED/PENDING)
        tmdb_id: Filter by TMDb ID
        media_type: Filter by media type (movie/tv)
        limit: Maximum number of records to return (default: 50)
    """
    if not history:
        return {"error": "Ingest functionality not configured"}
    return await ingest.get_ingest_history(history, status, tmdb_id, media_type, limit)


@mcp.tool()
async def check_duplicate(tmdb_id: int) -> dict:
    """Check if a TMDb ID has already been ingested.

    Args:
        tmdb_id: TMDb ID to check
    """
    if not history:
        return {"error": "Ingest functionality not configured"}
    return await ingest.check_duplicate(history, tmdb_id)


@mcp.tool()
async def get_ingest_statistics() -> dict:
    """Get ingest operation statistics."""
    if not history:
        return {"error": "Ingest functionality not configured"}
    return await ingest.get_ingest_statistics(history)


# =============================================================================
# Watcher Tools (only if watcher is initialized)
# =============================================================================

@mcp.tool()
async def get_watcher_status() -> dict:
    """Get file watcher status."""
    if not watcher:
        return {"error": "Watcher not configured (PLEX_INGEST_DIR not set)"}
    return await watcher.get_status()


@mcp.tool()
async def start_watcher() -> dict:
    """Start the file watcher."""
    if not watcher:
        return {"error": "Watcher not configured"}
    await watcher.start()
    return {"status": "started"}


@mcp.tool()
async def stop_watcher() -> dict:
    """Stop the file watcher."""
    if not watcher:
        return {"error": "Watcher not configured"}
    await watcher.stop()
    return {"status": "stopped"}


@mcp.tool()
async def configure_watcher(
    auto_ingest: Optional[bool] = None,
    confidence_threshold: Optional[float] = None,
    stability_seconds: Optional[int] = None
) -> dict:
    """Configure watcher settings.

    Args:
        auto_ingest: Enable/disable automatic ingestion
        confidence_threshold: Minimum confidence for auto-ingest (0.0-1.0)
        stability_seconds: File stability check duration in seconds
    """
    if not watcher:
        return {"error": "Watcher not configured"}
    return await watcher.configure(auto_ingest, confidence_threshold, stability_seconds)


@mcp.tool()
async def get_pending_queue() -> list[dict]:
    """Get pending ingest queue items awaiting review."""
    if not watcher:
        return {"error": "Watcher not configured"}
    return await watcher.get_pending_queue()


@mcp.tool()
async def approve_pending(source: str) -> dict:
    """Approve and process a pending queue item.

    Args:
        source: Source file path of pending item
    """
    if not watcher:
        return {"error": "Watcher not configured"}
    return await watcher.approve_pending(source)


@mcp.tool()
async def reject_pending(source: str) -> dict:
    """Reject and remove a pending queue item.

    Args:
        source: Source file path of pending item
    """
    if not watcher:
        return {"error": "Watcher not configured"}
    return await watcher.reject_pending(source)


# =============================================================================
# Transmission Tools (only if transmission_client is initialized)
# =============================================================================

@mcp.tool()
async def add_torrent(magnet_or_url: str, download_dir: Optional[str] = None) -> dict:
    """Add a torrent via magnet link or .torrent URL.

    Validation:
    - Accept only magnet URIs and explicit .torrent URLs
    - If download_dir is set, it must be under PLEX_INGEST_DIR

    Args:
        magnet_or_url: Magnet URI or .torrent file URL
        download_dir: Optional download directory (must be under PLEX_INGEST_DIR)
    """
    if not transmission_client:
        return {"error": "Transmission not configured (TRANSMISSION_URL not set)"}
    return await transmission.add_torrent(transmission_client, magnet_or_url, download_dir)


@mcp.tool()
async def list_torrents(status: Optional[str] = None) -> list[dict]:
    """List torrents with optional status filter (downloading/seeding/stopped/all).

    Args:
        status: Filter by status (downloading/seeding/stopped/all)
    """
    if not transmission_client:
        return [{"error": "Transmission not configured"}]
    return await transmission.list_torrents(transmission_client, status)


@mcp.tool()
async def get_torrent_status(torrent_id: int) -> dict:
    """Get detailed status of a specific torrent.

    Args:
        torrent_id: Torrent ID
    """
    if not transmission_client:
        return {"error": "Transmission not configured"}
    return await transmission.get_torrent_status(transmission_client, torrent_id)


@mcp.tool()
async def pause_torrent(torrent_id: int) -> dict:
    """Pause a torrent download.

    Args:
        torrent_id: Torrent ID
    """
    if not transmission_client:
        return {"error": "Transmission not configured"}
    return await transmission.pause_torrent(transmission_client, torrent_id)


@mcp.tool()
async def resume_torrent(torrent_id: int) -> dict:
    """Resume a paused torrent.

    Args:
        torrent_id: Torrent ID
    """
    if not transmission_client:
        return {"error": "Transmission not configured"}
    return await transmission.resume_torrent(transmission_client, torrent_id)


@mcp.tool()
async def remove_torrent(torrent_id: int, delete_data: bool = False) -> dict:
    """Remove a torrent and optionally delete downloaded data.

    Args:
        torrent_id: Torrent ID
        delete_data: Also delete downloaded data (default: False)
    """
    if not transmission_client:
        return {"error": "Transmission not configured"}
    return await transmission.remove_torrent(transmission_client, torrent_id, delete_data)


@mcp.tool()
async def get_transmission_stats() -> dict:
    """Get Transmission daemon statistics."""
    if not transmission_client:
        return {"error": "Transmission not configured"}
    return await transmission.get_transmission_stats(transmission_client)


# =============================================================================
# Library Season / Inventory Tools
# =============================================================================

@mcp.tool()
async def get_library_inventory(section_id: str) -> list[dict]:
    """Get all TV shows in a library section with their season numbers.

    Use this to see which seasons are already in Plex before comparing against
    TMDb to find missing content.

    Args:
        section_id: Library section ID (must be a TV show section)
    """
    return await library.get_library_inventory(plex_client, section_id)


@mcp.tool()
async def get_show_details(rating_key: str) -> dict:
    """Get detailed season and episode information for a specific TV show.

    Args:
        rating_key: Plex rating key for the show
    """
    return await library.get_show_details(plex_client, rating_key)


# =============================================================================
# Torrent Search Tools
# =============================================================================

@mcp.tool()
async def search_torrents(
    query: str,
    limit: int = 10,
    language: Optional[str] = None,
) -> dict:
    """Search for torrents by title or keyword across configured providers.

    When a language is specified, language-tagged query variants are generated
    and matching results are ranked higher.

    Args:
        query: Search query string (e.g. "Breaking Bad Season 5 1080p")
        limit: Maximum number of results (default 10)
        language: Optional language preference (e.g. "de", "german", "fr", "japanese").
                  Supported: German (de), French (fr), Spanish (es), Italian (it), Japanese (ja).
    """
    return await torrent_search_tools.search_torrents(torrent_search_client, query, limit, language)


@mcp.tool()
async def get_torrent_magnet(torrent_id: str) -> dict:
    """Get the magnet link for a torrent result ID returned by search_torrents.

    Args:
        torrent_id: ID string from a search_torrents result
    """
    return await torrent_search_tools.get_torrent_magnet(torrent_search_client, torrent_id)


@mcp.tool()
async def search_season(
    show_title: str,
    season: int,
    quality: str = "1080p",
    language: Optional[str] = None,
) -> dict:
    """Search for a complete season pack for a TV show.

    Runs optimised queries and returns ranked results preferring season packs
    over individual episodes. When a language is specified, language-specific
    query variants are included (e.g. German: adds "Deutsch", "GERMAN", "Staffel N").

    Args:
        show_title: TV show name (e.g. "Dark")
        season: Season number
        quality: Preferred quality string (default "1080p")
        language: Optional language code or name (e.g. "de", "german", "fr").
                  Supported: de/german, fr/french, es/spanish, it/italian, ja/japanese.
    """
    return await torrent_search_tools.search_season(
        torrent_search_client, show_title, season, quality, language=language
    )


# =============================================================================
# NAS Volume Mount Tools
# =============================================================================

@mcp.tool()
async def check_media_volume() -> dict:
    """Check if the NAS MEDIA volume is currently mounted and accessible.

    Uses VIDEODROME_NAS_IP, VIDEODROME_NAS_SHARE, and VIDEODROME_NAS_MOUNT_POINT
    from configuration.
    """
    return await nas_tools.check_media_volume()


@mcp.tool()
async def mount_media_volume(force_remount: bool = False) -> dict:
    """Mount the NAS MEDIA SMB share.

    On macOS uses 'open smb://…' (current user credentials).
    On Linux uses 'mount -t cifs'.

    Args:
        force_remount: Unmount and remount even if already mounted (macOS only)
    """
    return await nas_tools.mount_media_volume(force_remount)


# =============================================================================
# Discovery / Agentic Workflow Tools
# =============================================================================

@mcp.tool()
async def find_new_seasons(
    section_id: Optional[str] = None,
    show_filter: Optional[str] = None,
    auto_search_torrents: bool = False,
    quality: str = "1080p",
) -> dict:
    """Find TV shows in Plex that have new seasons available on TMDb.

    Compares the seasons currently in your Plex library against TMDb to
    identify which shows have seasons you don't yet have.

    Args:
        section_id: Plex TV library section ID (auto-detects if not provided)
        show_filter: Optional title substring to limit which shows are checked
        auto_search_torrents: If True, automatically search for torrents for each missing season
        quality: Quality string for torrent searches (default "1080p")
    """
    return await discovery_tools.find_new_seasons(
        plex_client=plex_client,
        matcher=matcher,
        section_id=section_id,
        show_filter=show_filter,
        auto_search_torrents=auto_search_torrents,
        torrent_client=torrent_search_client,
        quality=quality,
    )


@mcp.tool()
async def discover_top_rated_content(
    content_type: str = "both",
    min_rating: float = 7.5,
    genres: Optional[list] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    exclude_in_library: bool = True,
    max_results: int = 20,
    auto_queue: bool = False,
    quality: str = "1080p",
    include_newspaper_reviews: bool = True,
) -> dict:
    """Discover highly-rated movies and TV shows not yet in your Plex library.

    Uses TMDb trending and top-rated lists as the primary source.
    Optionally enriches ratings with:
        - IMDb and Rotten Tomatoes (when OMDB_API_KEY is configured)
        - The Guardian film reviews (scraped; falls back to archive.ph)
        - The Daily Telegraph reviews (scraped; falls back to archive.ph)

    Args:
        content_type: "movie", "tv", or "both" (default "both")
        min_rating: Minimum composite rating out of 10 (default 7.5)
        genres: Optional list of genre names to filter by (e.g. ["Drama", "Sci-Fi"])
        year_from: Optional start year filter (e.g. 2020)
        year_to: Optional end year filter (e.g. 2026)
        exclude_in_library: Skip content already in Plex (default True)
        max_results: Maximum number of recommendations (default 20)
        auto_queue: Search for torrents for the top 5 results (default False)
        quality: Quality string for torrent searches (default "1080p")
        include_newspaper_reviews: Fetch Guardian and Telegraph reviews for the shortlist (default True)
    """
    if (
        year_from is not None
        and year_to is not None
        and year_from > year_to
    ):
        return {"error": "Invalid year range: year_from must be less than or equal to year_to"}

    year_range = (
        (year_from, year_to)
        if year_from is not None or year_to is not None
        else None
    )
    return await discovery_tools.discover_top_rated_content(
        plex_client=plex_client,
        matcher=matcher,
        content_type=content_type,
        min_rating=min_rating,
        genres=genres,
        year_range=year_range,
        exclude_in_library=exclude_in_library,
        max_results=max_results,
        auto_queue=auto_queue,
        torrent_client=torrent_search_client,
        quality=quality,
        include_newspaper_reviews=include_newspaper_reviews,
    )


def validate_tool_safety(tool_name: str) -> None:
    """
    Validate that a tool operation is allowed to execute.

    Raises:
        ValueError: If operation is blocked
    """
    allowed, reason = validate_operation(tool_name)
    if not allowed:
        raise ValueError(reason)


def add_safety_metadata(result: dict, tool_name: str) -> dict:
    """
    Add safety metadata to tool result.

    Args:
        result: Original tool result
        tool_name: Name of the tool that was called

    Returns:
        Result with added safety metadata
    """
    safety_info = get_safety_metadata(tool_name)

    # Add safety metadata without overwriting existing data
    if isinstance(result, dict):
        result["_safety"] = safety_info

    return result


def main():
    """Main entry point."""
    logger.info("Videodrome MCP Server starting...")
    logger.info(f"Safety validation enabled for all {len(TOOL_SAFETY_MAP)} tools")
    mcp.run()


if __name__ == "__main__":
    main()
