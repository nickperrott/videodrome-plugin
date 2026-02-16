# /videodrome:rename - Preview and Execute Rename Plan

Generates and executes renaming plans to organize media files according to Plex naming conventions.

## Usage

```
/videodrome:rename <source_path> [--preview] [--execute] [--dry-run]
```

## Arguments

- `source_path` (required): File or directory to rename
- `--preview` (optional): Show proposed renames without executing (default)
- `--execute` (optional): Execute the rename plan
- `--dry-run` (optional): Validate rename operations without modifying files

## Examples

```
/videodrome:rename /data/ingest/new_movie.mkv --preview
/videodrome:rename /data/ingest/season1 --execute
/videodrome:rename /data/ingest --dry-run
```

## What it does

### Preview Mode (default)
1. Identifies media using guessit + TMDb
2. Constructs Plex-compliant paths:
   - Movies: `/Movies/Title (Year)/Title (Year) - Quality.ext`
   - TV: `/TV Shows/Title/Season 01/Title - S01E01 - Episode.ext`
3. Shows before/after paths
4. Displays confidence scores

### Execute Mode
1. Validates all paths are within PLEX_MEDIA_ROOT
2. Checks file extensions against whitelist
3. Creates destination directories
4. Copies or moves files to new locations
5. Logs operations to ingest history
6. Optionally triggers library scan

### Dry-run Mode
1. Simulates all operations
2. Validates paths and permissions
3. Reports what would happen without changes

## Safety Classification

**Write Operation** - Requires confirmation before execution.

Renaming moves files on disk. Preview and dry-run modes are read-only, but `--execute` modifies the filesystem.

## MCP Tools Used

- `preview_rename(source: str)` - Generate rename plan (read-only)
- `execute_naming_plan(plan: dict)` - Execute renames (write)
- `batch_identify(directory: str)` - Identify multiple files

## Output

Preview output:
```
Rename Plan for: /data/ingest/new_movies/

[1] The.Matrix.1999.mkv
    -> /Movies/The Matrix (1999)/The Matrix (1999) - 1080p BluRay.mkv
    Confidence: 0.95 ✓

[2] some.random.file.avi
    -> SKIPPED (confidence 0.45 - too low)

Summary: 1 file ready, 1 skipped
Total size: 8.2 GB
```

Execute output includes:
- Files moved/copied
- Errors or conflicts
- History log entries created
- Library scan triggered (if applicable)

## Notes

- Default behavior is preview mode for safety
- Minimum confidence threshold: 0.70
- Files below threshold are skipped with warnings
- Original files can be preserved (copy) or removed (move)
- All operations are logged to SQLite history database
