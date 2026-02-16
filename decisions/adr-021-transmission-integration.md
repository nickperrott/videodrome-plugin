# ADR-021: Transmission BitTorrent Integration

**Status:** Proposed
**Date:** 2026-02-16
**Deciders:** System Architect

---

## Context

The Plex MCP plugin currently handles:
- Media file identification (guessit + TMDb)
- Automated ingestion from watch folder
- File stability checking
- Duplicate detection
- Plex library management

However, the **download acquisition** step is manual. Users must:
1. Manually add torrents to Transmission
2. Wait for downloads to complete
3. Hope the watcher detects them
4. Review/approve pending items

This creates a **gap in automation** between "I want to download X" and "X is in my Plex library."

---

## Decision

Integrate Transmission BitTorrent client into the Plex MCP plugin to create a **complete automated pipeline**:

```
Add Torrent → Download → Detect Completion → Identify → Classify → Ingest → Scan Plex
```

### Architecture

#### 1. Add `transmission-rpc` Python Library
- Mature, well-maintained library (supports Transmission 2.40 → 4.0.6)
- Requires Python >= 3.10 (already met)
- Install: `pip install transmission-rpc`

#### 2. New Module: `server/transmission.py`
TransmissionClient wrapper managing:
- Connection to Transmission daemon (RPC)
- Adding torrents (magnet links, .torrent files)
- Monitoring torrent status
- Detecting completion events
- Retrieving download paths

#### 3. New Tools Module: `server/tools/transmission.py`
MCP tools for torrent management:
- `add_torrent(magnet_or_url, download_dir=None)` - Add torrent to download queue
  - `magnet_or_url` accepts only `magnet:` URIs or explicit `.torrent` URLs
  - If `download_dir` is provided, it must resolve under `PLEX_INGEST_DIR`
- `list_torrents(status_filter)` - List all/active/completed torrents
- `get_torrent_status(torrent_id)` - Get detailed status
- `pause_torrent(torrent_id)` - Pause download
- `resume_torrent(torrent_id)` - Resume download
- `remove_torrent(torrent_id, delete_data)` - Remove torrent
- `get_transmission_stats()` - Overall client stats

**Trust model:** Transmission MCP tools are intended for trusted local operators only.

#### 4. Enhanced Watcher: `server/watcher.py`
Add optional **Transmission completion monitoring**:

**Option A: Hybrid Mode** (Recommended)
- Watch filesystem for ANY new files (current behavior)
- Also poll Transmission for completed torrents
- When torrent completes → immediately process (no stability wait needed)
- Provides redundancy if Transmission API fails

**Option B: Transmission-Only Mode**
- Only monitor Transmission completion events
- Faster response (no file stability wait)
- Requires Transmission API to be available

#### 5. Configuration: `.env` Variables
```bash
# Existing
PLEX_URL=http://localhost:32400
PLEX_TOKEN=xxx
TMDB_API_KEY=xxx
PLEX_MEDIA_ROOT=/Volumes/MEDIA
PLEX_INGEST_DIR=/Volumes/MEDIA/transmission/downloads/complete
PLEX_AUTO_INGEST=true
PLEX_CONFIDENCE_THRESHOLD=0.85

# New - Transmission
TRANSMISSION_URL=http://localhost:9091/transmission/rpc
TRANSMISSION_USER=  # Optional
TRANSMISSION_PASSWORD=  # Optional
TRANSMISSION_POLL_INTERVAL=30  # Seconds between completion checks
TRANSMISSION_AUTO_REMOVE=false  # Remove torrent after successful ingest
```

**Constraint:** Transmission completed downloads must resolve under `PLEX_INGEST_DIR`.

---

## Implementation Plan

### Phase 1: Core Transmission Integration
**Files to Create:**
- `server/transmission.py` - Client wrapper
- `server/tools/transmission.py` - MCP tools
- Add to `server/main.py` - Initialize client, register tools

**MCP Tools Added:**
```python
@mcp.tool()
async def add_torrent(magnet_or_url: str, download_dir: Optional[str] = None) -> dict:
    """Add a torrent via magnet link or .torrent URL.

    Validation:
    - Accept only magnet URIs and explicit .torrent URLs
    - If download_dir is set, it must be under PLEX_INGEST_DIR
    """

@mcp.tool()
async def list_torrents(status: Optional[str] = None) -> list[dict]:
    """List torrents with optional status filter (downloading/seeding/stopped/all)."""

@mcp.tool()
async def get_torrent_status(torrent_id: int) -> dict:
    """Get detailed status of a specific torrent."""

@mcp.tool()
async def remove_torrent(torrent_id: int, delete_data: bool = False) -> dict:
    """Remove a torrent and optionally delete downloaded data."""

@mcp.tool()
async def get_transmission_stats() -> dict:
    """Get Transmission daemon statistics."""
```

### Phase 2: Watcher Enhancement
**Files to Modify:**
- `server/watcher.py` - Add Transmission polling

**New Watcher Features:**
1. **Completion Polling Loop** (runs every N seconds)
   - Poll Transmission for completed torrents
   - Filter: status == "seeding" or "stopped" AND progress == 100%
   - For each completed torrent:
     - Get download root path (file or directory)
     - Enumerate all valid video files (recursive for directories)
     - Check each file against history before processing
     - If new → immediately trigger `_process_stable_file()` (skip stability wait)
     - Optionally remove torrent after successful ingest

2. **Deduplication**
   - Track processed torrent `infoHash` values in history metadata
   - Track processed file paths per torrent hash
   - Prevent re-processing when torrents are re-added or IDs change

3. **Error Handling**
   - If Transmission unreachable → log warning, continue filesystem watching
   - Graceful degradation (filesystem-only mode)

### Phase 3: Workflow Enhancements
**Automated Pipeline:**
1. User (or Claude) calls `add_torrent("magnet:?xt=...")`
2. Transmission downloads in background
3. Watcher polls Transmission every 30s
4. Detects completion → identifies media
5. High confidence → auto-ingests to Plex library
6. Low confidence → adds to pending queue
7. Optionally removes torrent from Transmission
8. Triggers Plex library scan

**Manual Review Queue:**
- Pending items include torrent source info
- User approves → ingests and removes torrent
- User rejects → removes from queue (leaves torrent alone or removes it)

---

## Benefits

### 1. Complete Automation
- **Before:** Manual torrent addition → wait → manual review → ingest
- **After:** One command → fully automated to Plex

### 2. Faster Processing
- No 60-second file stability wait (Transmission completion is definitive)
- Immediate ingestion when download finishes

### 3. Better Resource Management
- Auto-remove completed torrents after ingestion
- Prevents disk space accumulation
- Keeps Transmission queue clean

### 4. Enhanced Intelligence
- Can query torrent metadata (name, size, source tracker)
- Better duplicate detection (same torrent added twice)
- Statistics tracking (download speeds, ratios)

### 5. User Experience
- Single command: `add_torrent("magnet:...")` and forget
- No manual file management needed
- Automatic cleanup of watch folder

---

## Risks & Mitigations

### Risk 1: Transmission Unavailable
**Mitigation:** Hybrid watcher mode (filesystem + Transmission)
**Fallback:** Filesystem watching still works independently

### Risk 2: Wrong Media in Torrent
**Mitigation:** Pending queue for low-confidence matches
**User Control:** Configure confidence threshold

### Risk 3: Torrent Removed Before Processing
**Mitigation:** Process immediately on completion
**Safety:** Copy files (not move) from download dir

### Risk 4: API Breaking Changes
**Mitigation:** transmission-rpc library handles compatibility
**Version Support:** Transmission 2.40+ (2011-present)

### Risk 5: Malformed Torrent Inputs
**Mitigation:** Validate `add_torrent` inputs (scheme and URL shape) before RPC calls
**Scope:** Trusted local operators, but still fail fast on invalid requests

---

## Alternatives Considered

### Alternative 1: Standalone Transmission MCP Server
**Pros:**
- Separation of concerns
- Reusable across projects

**Cons:**
- No integration with Plex workflow
- Manual coordination between servers
- Duplicate configuration

**Decision:** Rejected - Integration provides better UX

### Alternative 2: External Script + Cron
**Pros:**
- Simple, no code changes

**Cons:**
- No real-time detection
- Polling inefficiency
- Harder to manage

**Decision:** Rejected - Less elegant, poor UX

### Alternative 3: Transmission Post-Processing Script
**Pros:**
- Immediate notification on completion

**Cons:**
- Requires Transmission configuration changes
- Not portable
- Harder to debug

**Decision:** Rejected - Polling is acceptable at 30s interval

---

## Implementation Checklist

### Dependencies
- [ ] Add `transmission-rpc>=7.0.0` to `pyproject.toml` (`[project.dependencies]`)
- [ ] Add `watchdog>=4.0.0` (already present)

### Code Changes
- [ ] Create `server/transmission.py` - Client wrapper
- [ ] Create `server/tools/transmission.py` - MCP tools
- [ ] Modify `server/watcher.py` - Add completion polling
- [ ] Modify `server/main.py` - Initialize Transmission client
- [ ] Modify `server/history.py` - Track torrent IDs in metadata

### Configuration
- [ ] Add Transmission env vars to `.env.example`
- [ ] Document configuration in README

### Testing
- [ ] Unit tests for TransmissionClient
- [ ] Integration tests for watcher polling
- [ ] End-to-end test: add torrent → auto-ingest → verify in Plex

### Documentation
- [ ] Update README with Transmission setup
- [ ] Add workflow diagram (torrent → Plex)
- [ ] Document MCP tools in docstrings

---

## Success Criteria

1. ✅ Can add torrents via MCP tool
2. ✅ Watcher detects completed downloads within 60s
3. ✅ High-confidence matches auto-ingest without manual intervention
4. ✅ Low-confidence matches appear in pending queue
5. ✅ Completed torrents optionally removed after ingestion
6. ✅ System degrades gracefully if Transmission unavailable
7. ✅ No duplicate processing of same torrent
8. ✅ Complete pipeline documented and tested

---

## Timeline

- **Phase 1 (Core Integration):** 2-3 hours
- **Phase 2 (Watcher Enhancement):** 2-3 hours
- **Phase 3 (Testing & Documentation):** 2-3 hours
- **Total Estimate:** 6-9 hours

---

## References

- [transmission-rpc PyPI](https://pypi.org/project/transmission-rpc/)
- [transmission-rpc Documentation](https://transmission-rpc.readthedocs.io/)
- [Transmission RPC Specification](https://github.com/transmission/transmission/blob/main/docs/rpc-spec.md)
- [Existing Transmission MCP Server](https://mcpservers.org/servers/v-odoo-testing/transmission-mcp-server)
