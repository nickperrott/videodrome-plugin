# /videodrome:watch - Manage File Watcher

Control the background file watcher for automatic ingest processing.

## Usage

```
/videodrome:watch [start|stop|restart|status]
```

## Arguments

- `start` - Start the file watcher
- `stop` - Stop the file watcher
- `restart` - Restart the watcher (stop + start)
- `status` - Show current watcher status (default)

## Examples

```
/videodrome:watch
/videodrome:watch start
/videodrome:watch stop
/videodrome:watch restart
```

## What it does

### Start
1. Validates PLEX_INGEST_DIR is configured
2. Creates watchdog Observer for configured directory
3. Registers event handlers for file creation/modification
4. Starts background monitoring thread
5. Reports watcher status

### Stop
1. Stops the watchdog Observer
2. Processes any pending queue items
3. Gracefully shuts down monitoring thread
4. Reports final statistics

### Restart
1. Executes stop sequence
2. Waits for clean shutdown (5s timeout)
3. Executes start sequence
4. Reports new watcher status

### Status (default)
- Watcher running state
- Watched directory path
- Files processed since start
- Current queue size
- Last event timestamp

## How Auto-Ingest Works

When a file appears in the ingest directory:

1. **Stability Check** (60 seconds)
   - Monitor file size every 10 seconds
   - Proceed only when size is stable (no changes)
   - Prevents processing incomplete downloads

2. **Identification**
   - Parse filename with guessit
   - Query TMDb for matches
   - Calculate confidence score

3. **Routing Decision**
   - If confidence >= threshold AND auto_ingest enabled:
     - Automatically process (identify + rename + copy + scan)
     - Log to history
   - If confidence < threshold OR auto_ingest disabled:
     - Add to manual review queue
     - Notify user (if notifications configured)

4. **Cleanup**
   - Remove from watch queue
   - Update statistics

## Safety Classification

**Write Operation** - Requires confirmation when starting.

The watcher itself is read-only, but enabling it allows automatic file ingestion which modifies the filesystem.

Starting/stopping the watcher requires confirmation. Status checks are read-only.

## MCP Tools Used

- `start_watcher()` - Start file monitoring (write)
- `stop_watcher()` - Stop file monitoring (write)
- `get_watcher_status()` - Query watcher state (read-only)

## Output

```
File Watcher Status

Status: Running ✓
Watch Directory: /data/ingest
Started: 2024-02-10 12:00:00 (2 hours ago)

Auto-Ingest: Enabled
Confidence Threshold: 0.85

Statistics (since start):
- Files detected: 15
- Auto-processed: 12
- Queued for review: 3
- Errors: 0

Current Queue: 3 files
- movie1.mkv (waiting for stability check - 45s remaining)
- movie2.avi (ready for review - low confidence 0.62)
- tvshow.S01E01.mkv (ready for review - no TMDb match)

Last Event: 2024-02-10 14:32:15 (3 minutes ago)
Event: File created - /data/ingest/new.movie.mkv
```

## Configuration

Watcher behavior is controlled by environment variables:

```bash
PLEX_INGEST_DIR=/data/ingest          # Required - directory to monitor
PLEX_AUTO_INGEST=true                  # Enable automatic processing
PLEX_CONFIDENCE_THRESHOLD=0.85         # Minimum confidence for auto-ingest
PLEX_STABILITY_TIMEOUT=60              # Seconds to wait for stable file size
```

## Notes

- Watcher starts automatically if `auto_ingest: true` in config
- Only monitors configured PLEX_INGEST_DIR (not recursive subdirectories)
- Stability check prevents processing incomplete downloads
- Queue items persist across watcher restarts
- Multiple file events are deduplicated by file path
- Watcher uses minimal resources (~10MB RAM, <1% CPU)
