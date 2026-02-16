# /videodrome:identify - Identify Media Files

Analyzes media filenames using guessit and matches them against TMDb to identify movies/TV shows.

## Usage

```
/videodrome:identify <path_or_filename> [--batch]
```

## Arguments

- `path_or_filename` (required): File path, filename, or directory to analyze
- `--batch` (optional): Process entire directory recursively

## Examples

```
/videodrome:identify "The.Matrix.1999.1080p.BluRay.mkv"
/videodrome:identify /data/ingest/new_movies --batch
/videodrome:identify "Breaking.Bad.S01E01.720p.mkv"
```

## What it does

1. Parses filename using guessit to extract:
   - Title
   - Year
   - Season/Episode (for TV shows)
   - Quality, codec, source
2. Searches TMDb for matching titles
3. Calculates confidence score (0.0-1.0) based on:
   - Title similarity (40%)
   - Year match (30%)
   - Popularity ranking (15%)
   - Media type match (15%)
4. Returns top matches with metadata

## Safety Classification

**Read-only Operation** - Auto-approved, no confirmation needed.

This command only analyzes filenames and queries TMDb. It does not modify files or Plex libraries.

## MCP Tools Used

- `parse_filename(filename: str)` - Extract metadata from filename
- `search_tmdb(title: str, year: int | None, media_type: str)` - Search TMDb
- `batch_identify(directory: str)` - Process multiple files

## Output

Returns for each file:
```
File: The.Matrix.1999.1080p.BluRay.mkv
Parsed: The Matrix (1999) - movie
TMDb Match: The Matrix (1999) [ID: 603]
Confidence: 0.95
Genre: Action, Science Fiction
Rating: 8.7/10
Suggested Path: /Movies/The Matrix (1999)/The Matrix (1999) - 1080p BluRay.mkv
```

## Notes

- Cached TMDb results expire after 30 days
- Confidence threshold for auto-ingest defaults to 0.85
- Low-confidence matches (<0.70) are flagged for manual review
- Supports .mkv, .mp4, .avi, .m4v, .ts, .wmv, .mov
