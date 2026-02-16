# Plex Claude Plugin

A Claude MCP plugin for Plex Media Server administration. Provides automated library updates, intelligent media file naming, and automatic ingestion with folder watching.

## Features

- **Library Management**: List, search, and trigger scans on Plex libraries
- **Media Identification**: Parse filenames with guessit, verify against TMDb, construct Plex-compliant names
- **Batch Processing**: Identify and rename entire directories of media files in one operation
- **Auto-Ingestion**: Watch a folder for new media files, automatically identify, rename, copy to libraries, and trigger scans
- **Safety Model**: Three-tier tool classification (read/write/blocked) prevents accidental damage

## Architecture

Built as a Python MCP server using FastMCP, following the same patterns as the [TrueNAS Claude Plugin](https://github.com/nickperrott/truenas-claude-plugin).

```
Claude Desktop / Claude Code
  |  stdio (MCP)
  v
MCP Server (FastMCP)
  +-- PlexClient (python-plexapi)
  +-- MediaMatcher (guessit + TMDb)
  +-- FileManager (copy/rename/move)
  +-- IngestWatcher (watchdog)
  +-- IngestHistory (SQLite audit log)
```

## Requirements

- Python 3.11+
- Plex Media Server with API access
- TMDb API key (free at https://www.themoviedb.org/settings/api)
- uv package manager

## Quick Start

**📖 See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions!**

### 1. Interactive Configuration (Recommended)

```bash
cd videodrome-plugin/montreal-v1
./setup-config.sh
```

This wizard will:
- ✓ Guide you through all settings
- ✓ Test Plex and TMDb connections
- ✓ Save configuration to `.env` file

### 2. Test the Server

```bash
uv run --env-file .env videodrome
```

You should see: `Plex MCP Server started successfully!`

### 3. Connect to Claude

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "plex": {
      "command": "uv",
      "args": [
        "--directory", "/FULL/PATH/TO/videodrome-plugin/montreal-v1",
        "run", "--env-file", ".env", "videodrome"
      ]
    }
  }
}
```

**Important**: Use absolute path and restart Claude Desktop!

## Installation

### Claude Desktop (.mcpb)

Download the latest `.mcpb` file from [Releases](https://github.com/nickperrott/videodrome-plugin/releases) and open it with Claude Desktop.

### Claude Code (Plugin)

```bash
claude plugin install /path/to/videodrome-plugin
```

### Manual Configuration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "plex": {
      "command": "uv",
      "args": ["--directory", "/path/to/videodrome-plugin", "run", "videodrome"],
      "env": {
        "PLEX_URL": "http://192.168.1.100:32400",
        "PLEX_TOKEN": "your-plex-token",
        "TMDB_API_KEY": "your-tmdb-api-key",
        "PLEX_MEDIA_ROOT": "/data/media",
        "PLEX_INGEST_DIR": "/data/ingest"
      }
    }
  }
}
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PLEX_URL` | Yes | - | Plex server URL |
| `PLEX_TOKEN` | Yes | - | X-Plex-Token |
| `TMDB_API_KEY` | Yes | - | TMDb API key |
| `PLEX_MEDIA_ROOT` | Yes | - | Root path for media libraries |
| `PLEX_INGEST_DIR` | No | - | Folder to watch for new files |
| `PLEX_AUTO_INGEST` | No | `false` | Auto-process high-confidence matches |
| `PLEX_CONFIDENCE_THRESHOLD` | No | `0.85` | Minimum confidence for auto-processing |
| `PLEX_WATCHER_AUTO_START` | No | `false` | Start watcher on server launch |

## MCP Tools

### Read-only (auto-approved)
- `list_libraries` - List Plex library sections
- `list_recent` - Recently added items
- `search_library` - Search by title
- `get_server_info` - Server status
- `list_directory` - List local files
- `parse_filename` - Parse with guessit
- `search_tmdb` - Search TMDb
- `get_tmdb_details` / `get_tmdb_episode` - TMDb metadata
- `preview_rename` - Preview Plex-compliant name
- `batch_identify` - Identify all files in a directory
- `get_watcher_status` - Watcher state
- `get_ingest_queue` - Pending review items
- `get_ingest_history` - Past operations

### Write (require confirmation)
- `scan_library` - Trigger library scan
- `rename_file` / `copy_file` / `move_file` - File operations
- `create_directory` - Create folder structure
- `execute_naming_plan` - Batch rename/copy
- `execute_ingest` - Full ingest pipeline
- `start_watcher` / `stop_watcher` - Control watcher
- `approve_ingest` / `reject_ingest` - Handle queued items

## Claude Code Commands

| Command | Description |
|---------|-------------|
| `/videodrome:scan` | Trigger a library scan |
| `/videodrome:identify` | Identify a media file |
| `/videodrome:rename` | Rename files to Plex format |
| `/videodrome:ingest` | Process a folder of media |
| `/videodrome:status` | Show server status |
| `/videodrome:plan` | Preview a naming plan |
| `/videodrome:watch` | Control the file watcher |
| `/videodrome:review` | Review pending ingest items |

## Development

```bash
# Clone and setup
git clone https://github.com/nickperrott/videodrome-plugin.git
cd videodrome-plugin
uv sync --extra dev

# Run tests
pytest tests/ -v

# Run server locally
uv run videodrome
```

## Plex Naming Conventions

### Movies
```
/Movies/Movie Name (Year) {tmdb-ID}/Movie Name (Year) {tmdb-ID}.mkv
```

### TV Shows
```
/TV Shows/Show Name (Year)/Season 01/Show Name (Year) - s01e01 - Episode Title.mkv
```

## License

MIT
