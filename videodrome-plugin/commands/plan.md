# /videodrome:plan - Generate Ingest Plan

Creates a detailed ingest plan without executing any operations.

## Usage

```
/videodrome:plan <source_path> [--threshold=0.85] [--format=table|json]
```

## Arguments

- `source_path` (required): File or directory to analyze
- `--threshold=N` (optional): Minimum confidence score (0.0-1.0, default: 0.85)
- `--format=FORMAT` (optional): Output format (table or json, default: table)

## Examples

```
/videodrome:plan /data/downloads/movies
/videodrome:plan /data/downloads/season1 --threshold=0.90
/videodrome:plan /tmp/new_media --format=json
```

## What it does

1. **Discovery Phase**
   - Recursively scan source directory
   - Filter by supported extensions (.mkv, .mp4, etc.)
   - Calculate total file count and size

2. **Identification Phase**
   - Parse each filename with guessit
   - Query TMDb for matches
   - Calculate confidence scores

3. **Path Planning Phase**
   - Generate Plex-compliant destination paths
   - Check for conflicts or duplicates
   - Validate paths are within PLEX_MEDIA_ROOT

4. **Classification Phase**
   - Group by confidence tier:
     - High (>=threshold): Ready for auto-ingest
     - Medium (0.70-threshold): Manual review recommended
     - Low (<0.70): Requires manual identification

5. **Report Generation**
   - Summary statistics
   - Detailed per-file breakdown
   - Warnings and recommendations

## Safety Classification

**Read-only Operation** - Auto-approved, no confirmation needed.

Planning only analyzes files and generates reports. No files or metadata are modified.

## MCP Tools Used

- `batch_identify(directory: str)` - Identify all files
- `preview_rename(source: str)` - Generate destination paths
- `check_duplicates(tmdb_id: int)` - Detect existing content

## Output

### Table Format
```
Ingest Plan for: /data/downloads/movies/

Discovery: 5 files found (32.4 GB total)
Supported: 5 video files
Unsupported: 0 files skipped

Identification Results:
High Confidence (>=0.85): 3 files
Medium Confidence (0.70-0.85): 1 file
Low Confidence (<0.70): 1 file

HIGH CONFIDENCE - Ready for Auto-ingest
[1] The.Matrix.1999.mkv
    Confidence: 0.95
    TMDb: The Matrix (1999) [ID: 603]
    Destination: /Movies/The Matrix (1999)/The Matrix (1999) - 1080p BluRay.mkv
    Size: 8.2 GB
    Status: READY ✓

[2] Inception.2010.mkv
    Confidence: 0.92
    TMDb: Inception (2010) [ID: 27205]
    Destination: /Movies/Inception (2010)/Inception (2010) - 1080p BluRay.mkv
    Size: 12.1 GB
    Status: READY ✓

MEDIUM CONFIDENCE - Review Recommended
[3] The.Thing.2011.mkv
    Confidence: 0.78
    TMDb: The Thing (2011) [ID: 64686]
    Destination: /Movies/The Thing (2011)/The Thing (2011) - 1080p BluRay.mkv
    Size: 7.8 GB
    Warning: Multiple matches found (1982 vs 2011 version)

LOW CONFIDENCE - Manual Review Required
[4] random.movie.avi
    Confidence: 0.45
    Parsed: random movie (no year)
    TMDb: No confident match
    Status: REQUIRES_MANUAL_REVIEW

Summary:
- Ready for ingest: 2 files (20.3 GB)
- Needs review: 2 files (8.2 GB)
- Total: 4 files (28.5 GB)

Recommendation: Run /videodrome:ingest with --auto flag for high-confidence files
```

### JSON Format
Returns structured JSON suitable for programmatic processing:
```json
{
  "source_path": "/data/downloads/movies",
  "discovered": 5,
  "total_size_gb": 32.4,
  "confidence_threshold": 0.85,
  "tiers": {
    "high": {
      "count": 2,
      "total_size_gb": 20.3,
      "files": [...]
    },
    "medium": {
      "count": 1,
      "total_size_gb": 7.8,
      "files": [...]
    },
    "low": {
      "count": 1,
      "total_size_gb": 0.4,
      "files": [...]
    }
  }
}
```

## Notes

- Plan generation can take time for large directories (1-2 seconds per file)
- TMDb queries are cached to speed up repeated planning
- Duplicate detection checks against ingest history database
- JSON format useful for automation or external processing
- Plans are not saved - re-run command to regenerate
