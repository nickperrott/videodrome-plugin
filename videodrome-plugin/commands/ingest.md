# /videodrome:ingest - Execute Full Ingest Pipeline

Runs the complete ingest pipeline: identify -> rename -> copy -> scan -> log.

## Usage

```
/videodrome:ingest <source_path> [--auto] [--threshold=0.85]
```

## Arguments

- `source_path` (required): File or directory to ingest
- `--auto` (optional): Auto-process high-confidence matches without confirmation
- `--threshold=N` (optional): Minimum confidence score (0.0-1.0, default: 0.85)

## Examples

```
/videodrome:ingest /data/downloads/Movie.2024.mkv
/videodrome:ingest /data/downloads/season1 --auto --threshold=0.90
/videodrome:ingest /tmp/new_media
```

## What it does

1. **Identify Phase**
   - Parse all media files using guessit
   - Search TMDb for each title
   - Calculate confidence scores

2. **Planning Phase**
   - Generate rename plan for high-confidence matches
   - Flag low-confidence files for review
   - Validate destination paths

3. **Execution Phase**
   - Create target directories
   - Copy files to Plex libraries
   - Apply Plex naming conventions
   - Verify file integrity (size check)

4. **Integration Phase**
   - Trigger library scan for affected sections
   - Log all operations to history database
   - Archive or cleanup source files (optional)

5. **Reporting Phase**
   - Summary of ingested files
   - TMDb metadata for each item
   - Any errors or warnings

## Safety Classification

**Write Operation** - Requires confirmation before execution.

Ingest modifies the filesystem and Plex libraries. The `--auto` flag still requires initial setup confirmation but skips per-file prompts.

## MCP Tools Used

- `batch_identify(directory: str)` - Identify all files
- `execute_ingest(plan: dict, auto_approve: bool)` - Execute full pipeline
- `scan_library(library_name: str | None)` - Refresh Plex
- `log_ingest_history(operations: list)` - Record to database

## Output

```
Ingest Report for: /data/downloads/movies/

Identified: 3 files
High confidence (>=0.85): 2 files
Low confidence (<0.85): 1 file

[1] The.Matrix.1999.mkv ✓
    TMDb: The Matrix (1999) [ID: 603]
    Confidence: 0.95
    Destination: /Movies/The Matrix (1999)/
    Status: COPIED (8.2 GB)

[2] Inception.2010.mkv ✓
    TMDb: Inception (2010) [ID: 27205]
    Confidence: 0.92
    Destination: /Movies/Inception (2010)/
    Status: COPIED (12.1 GB)

[3] unknown.movie.avi ⚠
    Confidence: 0.62 (below threshold)
    Status: SKIPPED - manual review required

Summary:
- Ingested: 2 files (20.3 GB)
- Skipped: 1 file (requires review)
- Libraries scanned: Movies
- History entries: 2
```

## Notes

- Default threshold is 0.85 (85% confidence)
- Files below threshold are never auto-ingested
- Source files are preserved by default (copy, not move)
- Set `auto_ingest: true` in config for background processing
- All operations logged with timestamps and TMDb IDs
- Duplicate detection prevents re-ingesting the same content
