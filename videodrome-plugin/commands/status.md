# /videodrome:status - Server and Library Status

Display current status of Plex server, libraries, and ingest queue.

## Usage

```
/videodrome:status [--libraries] [--queue] [--history]
```

## Arguments

- `--libraries` (optional): Show detailed library statistics
- `--queue` (optional): Show pending ingest queue items
- `--history` (optional): Show recent ingest history (last 10)

## Examples

```
/videodrome:status
/videodrome:status --libraries
/videodrome:status --queue --history
```

## What it does

### Default Status
- Plex server connectivity and version
- Total libraries and item counts
- Current scan/refresh operations
- Watcher status (running/stopped)
- Ingest queue size

### With --libraries
- Per-library item counts
- Last scan timestamps
- Library paths and types
- Storage usage (if available)

### With --queue
- Files waiting for manual review
- Pending low-confidence matches
- Queue processing status

### With --history
- Recent ingest operations (last 10)
- Success/failure status
- Timestamps and file sizes
- TMDb match information

## Safety Classification

**Read-only Operation** - Auto-approved, no confirmation needed.

Status checks only query data without modifying anything.

## MCP Tools Used

- `get_server_info()` - Server details and version
- `list_libraries()` - Library information
- `get_library_stats(library_name: str)` - Detailed stats
- `get_ingest_queue()` - Pending items
- `query_history(limit: int, filters: dict)` - Recent operations

## Output

```
Plex Media Server Status

Server: plex.local (192.168.1.100:32400)
Version: 1.40.0.7998
Status: Connected ✓

Libraries: 3 total
- Movies: 847 items (last scan: 2 hours ago)
- TV Shows: 124 shows, 2,451 episodes (last scan: 5 minutes ago)
- Music: 3,201 albums (last scan: 1 day ago)

Watcher: Running ✓
Watch Directory: /data/ingest
Queue: 3 files pending review

Recent Ingest History (last 10):
[1] 2024-02-10 14:32 - The Matrix (1999) [COPIED] 8.2 GB
[2] 2024-02-10 14:30 - Inception (2010) [COPIED] 12.1 GB
[3] 2024-02-10 13:15 - Breaking Bad S01E01 [COPIED] 1.4 GB
...
```

## Notes

- Status checks are cached for 60 seconds to reduce API load
- Queue shows only items requiring manual intervention
- History can be filtered by date, status, or TMDb ID
- Watcher status indicates if file monitoring is active
