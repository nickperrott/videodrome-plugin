# Plex Claude Plugin - Architecture

## System Architecture

```
Claude Desktop / Claude Code
  |
  | stdio (MCP protocol)
  v
MCP Server (FastMCP)
  server/main.py
  |
  +-- PlexClient (python-plexapi)
  |     connects to http://{ip}:32400
  |     async wrapping via asyncio.to_thread()
  |
  +-- TMDbClient (tmdbsimple)
  |     connects to api.themoviedb.org
  |     results cached in SQLite (30-day TTL)
  |
  +-- MediaMatcher
  |     guessit filename parsing
  |     TMDb lookup + confidence scoring
  |     Plex-compliant path construction
  |
  +-- FileManager
  |     copy/rename/move with path restrictions
  |     extension whitelist enforcement
  |     batch plan execution
  |
  +-- IngestWatcher (watchdog)
  |     monitors PLEX_INGEST_DIR
  |     stability check (60s stable file size)
  |     auto-process high confidence matches
  |     queue low confidence for Claude review
  |
  +-- IngestHistory (SQLite)
        full audit trail of all operations
        duplicate detection by TMDb ID
```

## Key Design Decisions

### Protocol-Based Client Pattern
The PlexClient uses a Python Protocol class to define the interface, with a factory function that reads environment variables. This follows the same pattern as the TrueNAS plugin's dual-backend approach, though Plex only needs one backend (HTTP via python-plexapi).

### Async Wrapping
python-plexapi is synchronous. All calls are wrapped with `asyncio.to_thread()` to avoid blocking the FastMCP event loop. This is the same pattern used in the TrueNAS plugin's WebSocket backend.

### Media Identification Pipeline
1. `guessit(filename)` extracts structured metadata (title, year, type, season, episode)
2. TMDb search verifies the match and provides canonical metadata
3. Confidence scoring (0.0-1.0) determines automation eligibility
4. Plex-compliant paths are constructed using TMDb data

### Confidence Scoring
- Title similarity (Levenshtein/SequenceMatcher): 40% weight
- Year match (exact=1.0, +/-1=0.8, missing=0.5): 30% weight
- TMDb popularity (normalized): 15% weight
- Type match (guessit type matches TMDb media_type): 15% weight

### Three-Tier Safety Model
- **Read-only tools**: Auto-approved (list, search, parse, preview)
- **Write tools**: Require user confirmation (scan, rename, copy, ingest)
- **Destructive tools**: Blocked entirely (delete operations)

### Watcher Architecture
The watchdog library uses OS-level file system events (inotify/FSEvents/kqueue) running in a separate thread. Events are bridged to the asyncio event loop via `loop.call_soon_threadsafe()`. A stability check polls file size every 10 seconds and considers a file stable after 60 seconds of no change.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PLEX_URL` | Yes | Plex server URL (e.g., `http://192.168.1.100:32400`) |
| `PLEX_TOKEN` | Yes | X-Plex-Token for authentication |
| `TMDB_API_KEY` | Yes | TMDb API key for media identification |
| `PLEX_MEDIA_ROOT` | Yes | Root path for media libraries |
| `PLEX_INGEST_DIR` | No | Directory to watch for new files |
| `PLEX_AUTO_INGEST` | No | Enable auto-processing (default: false) |
| `PLEX_CONFIDENCE_THRESHOLD` | No | Auto-process threshold (default: 0.85) |
| `PLEX_WATCHER_AUTO_START` | No | Start watcher on server launch (default: false) |

## MCP Tools Summary

### Read-only (13 tools)
| Tool | Description |
|------|-------------|
| `list_libraries` | List all Plex library sections |
| `list_recent` | Recently added items in a section |
| `search_library` | Search by title |
| `get_server_info` | Server name, version, platform |
| `list_directory` | List files in a local path |
| `parse_filename` | Parse a filename via guessit |
| `search_tmdb` | Search TMDb by title/year |
| `get_tmdb_details` | TMDb movie/show details |
| `get_tmdb_episode` | TMDb episode details |
| `preview_rename` | Preview Plex-compliant name |
| `batch_identify` | Scan directory and match all files |
| `get_watcher_status` | Watcher state and queue depth |
| `get_ingest_queue` | Pending items awaiting review |
| `get_ingest_history` | Query past ingest operations |

### Write (12 tools)
| Tool | Description |
|------|-------------|
| `scan_library` | Trigger library scan |
| `rename_file` | Rename a single file |
| `copy_file` | Copy a file |
| `move_file` | Move a file |
| `create_directory` | Create folder structure |
| `execute_naming_plan` | Execute batch rename/copy |
| `execute_ingest` | Full ingest pipeline |
| `start_watcher` | Start file watcher |
| `stop_watcher` | Stop file watcher |
| `approve_ingest` | Approve pending item |
| `reject_ingest` | Reject pending item |
| `configure_watcher` | Update watcher settings |

### Blocked (2 tools)
| Tool | Description |
|------|-------------|
| `delete_file` | Blocked - prevents accidental deletion |
| `delete_library` | Blocked - prevents library destruction |
