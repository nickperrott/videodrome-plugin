# Plex Media Server Plugin for Claude Code

Comprehensive plugin for managing Plex Media Server through Claude. Provides library management, media identification, automated ingest, and file watching capabilities.

## Overview

This plugin adds Plex administration commands to Claude Code, allowing you to:
- Manage Plex libraries (scan, search, status)
- Identify media files using TMDb
- Rename and organize files with Plex conventions
- Automate media ingestion with confidence scoring
- Monitor directories for new content
- Review and process low-confidence matches

## Commands

### /videodrome:scan - Scan Plex Library

Triggers a library scan to refresh Plex's metadata.

```
/videodrome:scan [library_name]
```

Examples:
- `/videodrome:scan Movies` - Scan Movies library only
- `/videodrome:scan` - Scan all libraries

**Safety: WRITE** - Requires confirmation (resource-intensive)

---

### /videodrome:identify - Identify Media Files

Analyzes media filenames using guessit and matches against TMDb.

```
/videodrome:identify <path_or_filename> [--batch]
```

Examples:
- `/videodrome:identify "The.Matrix.1999.1080p.mkv"`
- `/videodrome:identify /data/ingest --batch`

**Safety: READ** - Auto-approved (analysis only, no modifications)

---

### /videodrome:rename - Preview and Execute Rename Plan

Generates and executes renaming plans for Plex naming conventions.

```
/videodrome:rename <source_path> [--preview|--execute|--dry-run]
```

Examples:
- `/videodrome:rename /data/ingest/movie.mkv --preview` (default)
- `/videodrome:rename /data/ingest/season1 --execute`

**Safety: WRITE** - Requires confirmation for --execute

---

### /videodrome:ingest - Execute Full Ingest Pipeline

Runs complete ingest: identify → rename → copy → scan → log.

```
/videodrome:ingest <source_path> [--auto] [--threshold=0.85]
```

Examples:
- `/videodrome:ingest /data/downloads/Movie.2024.mkv`
- `/videodrome:ingest /data/downloads/batch --auto --threshold=0.90`

**Safety: WRITE** - Requires confirmation (modifies filesystem and Plex)

---

### /videodrome:status - Server and Library Status

Display current Plex server, library, and queue status.

```
/videodrome:status [--libraries] [--queue] [--history]
```

Examples:
- `/videodrome:status` - Basic status
- `/videodrome:status --libraries --queue` - Detailed view

**Safety: READ** - Auto-approved (queries only)

---

### /videodrome:plan - Generate Ingest Plan

Creates detailed ingest plan without executing operations.

```
/videodrome:plan <source_path> [--threshold=0.85] [--format=table|json]
```

Examples:
- `/videodrome:plan /data/downloads/movies`
- `/videodrome:plan /data/downloads --format=json`

**Safety: READ** - Auto-approved (planning only, no execution)

---

### /videodrome:watch - Manage File Watcher

Control background file watcher for automatic ingest.

```
/videodrome:watch [start|stop|restart|status]
```

Examples:
- `/videodrome:watch` - Show status
- `/videodrome:watch start` - Start monitoring
- `/videodrome:watch stop` - Stop monitoring

**Safety: WRITE** - Requires confirmation for start/stop/restart

---

### /videodrome:review - Review Pending Queue Items

Review and process files in manual review queue.

```
/videodrome:review [--all] [--file=<path>] [--approve] [--reject]
```

Examples:
- `/videodrome:review` - List pending items
- `/videodrome:review --file=/data/ingest/movie.mkv --approve`

**Safety: MIXED** - List is READ, approve/reject is WRITE

---

## Agents

The plugin includes four specialized agents that coordinate operations:

### Library Management Agent
- Handles Plex library queries and scans
- Reports library statistics and health
- Coordinates post-ingest library refreshes

### Media Identification Agent
- Parses filenames using guessit
- Matches against TMDb with confidence scoring
- Generates Plex-compliant file paths

### Ingest Processing Agent
- Executes file copy/rename operations
- Manages ingest history database
- Handles manual review queue

### File Watcher Agent
- Monitors ingest directory for new files
- Routes files by confidence score
- Coordinates automatic processing

## Safety Model

### Three-Tier Classification

**READ (Auto-approved)**
- Library queries: `list_libraries`, `search_library`, `get_server_info`
- Media identification: `parse_filename`, `search_tmdb`, `preview_rename`
- Status checks: `get_ingest_queue`, `query_history`, `get_watcher_status`

**WRITE (Require confirmation)**
- Library operations: `scan_library`, `refresh_metadata`
- File operations: `execute_ingest`, `copy_file`, `rename_file`
- Queue management: `approve_queue_item`, `reject_queue_item`
- Watcher control: `start_watcher`, `stop_watcher`

**BLOCKED (Always denied)**
- Destructive operations: `delete_file`, `delete_library`, `remove_file`

## Configuration

Required environment variables:

```bash
PLEX_URL=http://192.168.1.100:32400
PLEX_TOKEN=your_plex_token
TMDB_API_KEY=your_tmdb_api_key
PLEX_MEDIA_ROOT=/data/media
```

Optional:

```bash
PLEX_INGEST_DIR=/data/ingest
PLEX_AUTO_INGEST=true
PLEX_CONFIDENCE_THRESHOLD=0.85
PLEX_STABILITY_TIMEOUT=60
```

## Confidence Scoring

Files are scored 0.0-1.0 based on:
- **Title similarity (40%)**: Levenshtein distance comparison
- **Year match (30%)**: Exact year, within 1 year, or missing
- **Popularity (15%)**: TMDb vote count and rating
- **Media type (15%)**: Correct movie/TV classification

**Thresholds:**
- High (≥0.85): Auto-ingest eligible
- Medium (0.70-0.84): Review recommended
- Low (<0.70): Manual intervention required

## Plex Naming Conventions

### Movies
```
/Movies/Title (Year)/Title (Year) - Quality.ext
```

Example:
```
/Movies/The Matrix (1999)/The Matrix (1999) - 1080p BluRay.mkv
```

### TV Shows
```
/TV Shows/Title/Season NN/Title - SNNENN - Episode.ext
```

Example:
```
/TV Shows/Breaking Bad/Season 01/Breaking Bad - S01E01 - Pilot.mkv
```

## Typical Workflows

### One-time Import
```
1. /videodrome:identify /data/downloads/movies --batch
2. /videodrome:plan /data/downloads/movies
3. /videodrome:ingest /data/downloads/movies
4. /videodrome:status --history
```

### Automated Monitoring
```
1. Configure PLEX_AUTO_INGEST=true and PLEX_INGEST_DIR
2. /videodrome:watch start
3. Drop files into ingest directory
4. High-confidence files auto-process
5. /videodrome:review for low-confidence matches
```

### Manual Review
```
1. /videodrome:review --all
2. /videodrome:review --file=/path/to/file.mkv
3. /videodrome:review --file=/path/to/file.mkv --approve
```

## Technical Details

### Backend
- Python 3.11+ with FastMCP
- python-plexapi for Plex integration
- guessit for filename parsing
- tmdbsimple for TMDb API
- watchdog for file monitoring
- SQLite for caching and history

### Cache Strategy
- TMDb results cached 30 days
- Server status cached 60 seconds
- Library lists cached 60 seconds

### Performance
- Batch operations: ~2s per file (network dependent)
- Parallel TMDb queries: max 5 concurrent
- Watcher overhead: <10MB RAM, <1% CPU

### File Support
Supported extensions: `.mkv`, `.mp4`, `.avi`, `.m4v`, `.ts`, `.wmv`, `.mov`

## Troubleshooting

### "Could not connect to Plex server"
- Check PLEX_URL is correct and reachable
- Verify PLEX_TOKEN is valid
- Ensure Plex server is running

### "TMDb API rate limit exceeded"
- Wait 10 seconds and retry
- Check TMDB_API_KEY is valid
- Cache will reduce API calls over time

### "Path outside allowed directory"
- All paths must be within PLEX_MEDIA_ROOT or PLEX_INGEST_DIR
- Check path configuration in environment variables

### "Low confidence match"
- Add year to filename for better matching
- Check TMDb for correct title spelling
- Use manual review to select correct match

### "File watcher not detecting files"
- Verify PLEX_INGEST_DIR is configured
- Check directory permissions
- Ensure files have stable size (not actively downloading)

## Support

For issues, feature requests, or questions:
- GitHub: https://github.com/yourusername/videodrome-plugin
- Documentation: See `/docs/` directory
- Examples: See `/examples/` directory

## License

MIT License - See LICENSE file for details
