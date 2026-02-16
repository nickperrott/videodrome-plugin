# /videodrome:scan - Scan Plex Library

Triggers a library scan to refresh Plex's metadata for all or specific libraries.

## Usage

```
/videodrome:scan [library_name]
```

## Arguments

- `library_name` (optional): Name of specific library to scan. If omitted, scans all libraries.

## Examples

```
/videodrome:scan Movies
/videodrome:scan TV Shows
/videodrome:scan
```

## What it does

1. Connects to configured Plex Media Server
2. If library_name provided:
   - Finds the specified library
   - Triggers a scan for that library only
3. If no library_name:
   - Lists all available libraries
   - Triggers scan for each library sequentially
4. Reports scan status and completion

## Safety Classification

**Write Operation** - Requires confirmation before execution.

Scanning modifies Plex's metadata database and triggers filesystem indexing. While non-destructive to media files, it can be resource-intensive on the server.

## MCP Tools Used

- `scan_library(library_name: str | None)` - Triggers Plex library scan
- `list_libraries()` - Lists available libraries (when scanning all)

## Output

Returns a summary of:
- Libraries scanned
- Scan trigger status
- Estimated time to completion (if available from Plex API)

## Notes

- Scanning is an asynchronous operation on the Plex server
- Large libraries may take several minutes to complete
- The command returns immediately after triggering the scan
- Use `/videodrome:status` to check scan progress
