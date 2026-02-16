# /videodrome:review - Review Pending Queue Items

Review and process files in the manual review queue (low-confidence matches).

## Usage

```
/videodrome:review [--all] [--file=<path>] [--approve] [--reject]
```

## Arguments

- `--all` (optional): Show all pending queue items
- `--file=PATH` (optional): Review specific file
- `--approve` (optional): Approve and ingest the file
- `--reject` (optional): Reject and remove from queue

## Examples

```
/videodrome:review
/videodrome:review --all
/videodrome:review --file=/data/ingest/movie.mkv
/videodrome:review --file=/data/ingest/movie.mkv --approve
/videodrome:review --file=/data/ingest/movie.mkv --reject
```

## What it does

### List Mode (default)
1. Query ingest queue for pending items
2. Display items requiring manual review
3. Show identification results and confidence scores
4. Present suggested matches from TMDb
5. Provide commands for approval/rejection

### Single File Review
1. Load file from queue
2. Display parsed metadata from guessit
3. Show top TMDb matches with confidence scores
4. Present destination path preview
5. Offer interactive approval/rejection

### Approve Action
1. Validate user confirmation
2. Execute ingest pipeline for approved item
3. Remove from queue
4. Log to history database

### Reject Action
1. Remove item from queue
2. Optionally move to rejected directory
3. Log rejection reason

## Safety Classification

**Mixed Operation**

- List/review: Read-only (auto-approved)
- Approve: Write operation (requires confirmation)
- Reject: Write operation (requires confirmation)

## MCP Tools Used

- `get_ingest_queue()` - Retrieve pending items (read-only)
- `get_queue_item(file_path: str)` - Get specific item details (read-only)
- `approve_queue_item(file_path: str)` - Process approved item (write)
- `reject_queue_item(file_path: str, reason: str)` - Remove rejected item (write)

## Output

### List All Items
```
Manual Review Queue: 3 items

[1] /data/ingest/The.Thing.mkv
    Parsed: The Thing (no year)
    Confidence: 0.68

    Possible Matches:
    A) The Thing (1982) [ID: 1091] - Confidence: 0.68
       Genre: Horror, Science Fiction
       Rating: 8.1/10

    B) The Thing (2011) [ID: 64686] - Confidence: 0.66
       Genre: Horror, Science Fiction
       Rating: 6.2/10

    Command: /videodrome:review --file=/data/ingest/The.Thing.mkv

[2] /data/ingest/random.movie.avi
    Parsed: random movie (no year)
    Confidence: 0.45
    No confident TMDb matches found
    Recommendation: Rename file or provide more metadata

[3] /data/ingest/foreign.film.mkv
    Parsed: foreign film (no year)
    Confidence: 0.52
    Multiple ambiguous matches - manual selection required
```

### Single File Review
```
Queue Item: /data/ingest/The.Thing.mkv

Parsed Metadata:
- Title: The Thing
- Year: Not detected
- Type: movie
- Quality: Unknown
- Size: 7.8 GB

TMDb Search Results:

[1] The Thing (1982) ★★★ RECOMMENDED
    TMDb ID: 1091
    Confidence: 0.68
    Genre: Horror, Mystery, Science Fiction
    Rating: 8.1/10 (3,429 votes)
    Director: John Carpenter

    Destination Path:
    /Movies/The Thing (1982)/The Thing (1982).mkv

    Confidence Breakdown:
    - Title similarity: 100% (exact match)
    - Year match: 0% (no year in filename)
    - Popularity: 85% (highly rated)
    - Type match: 100% (movie)

[2] The Thing (2011)
    TMDb ID: 64686
    Confidence: 0.66
    Genre: Horror, Mystery, Science Fiction
    Rating: 6.2/10 (1,847 votes)
    Director: Matthijs van Heijningen Jr.

    Destination Path:
    /Movies/The Thing (2011)/The Thing (2011).mkv

Actions:
- To approve match #1: /videodrome:review --file=/data/ingest/The.Thing.mkv --approve
- To reject: /videodrome:review --file=/data/ingest/The.Thing.mkv --reject
- To search manually: /videodrome:identify "The Thing 1982"
```

### Approval Output
```
Approved: /data/ingest/The.Thing.mkv

Ingesting as: The Thing (1982) [TMDb: 1091]
Destination: /Movies/The Thing (1982)/The Thing (1982).mkv

Processing:
✓ Created directory: /Movies/The Thing (1982)/
✓ Copied file: 7.8 GB
✓ Verified integrity
✓ Triggered library scan: Movies
✓ Logged to history

Status: COMPLETED
Removed from queue
```

## Notes

- Queue items are added by the watcher or failed auto-ingest attempts
- Items remain in queue until explicitly approved or rejected
- Rejecting an item does not delete the source file
- Multiple matches are sorted by confidence score (highest first)
- Manual TMDb ID can be provided: `--tmdb-id=1091`
- Queue is persistent across server restarts
