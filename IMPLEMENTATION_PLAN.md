# Implementation Plan

## Overview

Build a full-featured MCP plugin for Plex Media Server administration with background file watching and auto-ingestion. Follows the TrueNAS Claude plugin patterns.

**Stack:** Python 3.11+, FastMCP, uv + hatchling, .mcpb + Claude Code plugin distribution

**Dependencies:** mcp>=1.2.0, plexapi>=4.18.0, guessit>=3.8.0, tmdbsimple>=2.9.0, aiosqlite>=0.20.0, watchdog>=4.0.0

**Dev dependencies:** pytest>=8.0, pytest-asyncio>=0.23, pytest-mock>=3.12, aioresponses>=0.7

## TDD Approach

Every module is built tests-first. For each component:
1. Write test file with all test cases (happy path, edge cases, error conditions)
2. Run tests - confirm they fail (red)
3. Implement the minimum code to pass (green)
4. Refactor if needed

Tests use mocks for all external services (Plex API, TMDb API, filesystem). No real Plex server or TMDb account needed to run the test suite.

### Test Structure
```
tests/
  conftest.py                 # Shared fixtures: mock PlexServer, mock TMDb responses, temp dirs
  test_client.py              # PlexClient protocol, factory, async wrapping
  test_tmdb_cache.py          # SQLite cache: store, retrieve, TTL expiry, key collisions
  test_matcher.py             # guessit parsing, TMDb matching, confidence scoring, path construction
  test_files.py               # FileManager: copy, rename, path restrictions, extension whitelist
  test_watcher.py             # IngestWatcher: file detection, stability check, queue routing
  test_history.py             # IngestHistory: log operations, query filters, duplicate detection
  test_tools_library.py       # Library MCP tools integration
  test_tools_media.py         # Media MCP tools integration
  test_tools_ingest.py        # Ingest MCP tools integration
  test_tools_system.py        # System MCP tools integration
  test_safety_hook.py         # Three-tier classification (read/write/blocked)
  test_plugin_structure.py    # Plugin directory structure, manifest, markdown validation
```

## Parallel Implementation with Subagents

The implementation is split into 4 independent work streams that can run as concurrent subagents, plus a final integration phase.

### Phase 1: Scaffolding (sequential, single agent)
Create repo structure, pyproject.toml, conftest.py with shared fixtures, all __init__.py files.

### Phase 2: Core Modules (4 parallel subagents)

**Subagent A: PlexClient + Library/System Tools**
- Files: server/client.py, server/tools/library.py, server/tools/system.py
- Tests: tests/test_client.py, tests/test_tools_library.py, tests/test_tools_system.py
- Scope: PlexClient protocol, factory, async wrapping, list_libraries, scan_library, search_library, list_recent, get_server_info

**Subagent B: TMDb Cache + MediaMatcher + Media Tools**
- Files: server/tmdb_cache.py, server/matcher.py, server/tools/media.py
- Tests: tests/test_tmdb_cache.py, tests/test_matcher.py, tests/test_tools_media.py
- Scope: SQLite cache, guessit pipeline, confidence scoring, Plex path construction, parse_filename, search_tmdb, preview_rename, batch_identify

**Subagent C: FileManager + IngestHistory + Ingest Tools**
- Files: server/files.py, server/history.py, server/tools/ingest.py
- Tests: tests/test_files.py, tests/test_history.py, tests/test_tools_ingest.py
- Scope: File copy/rename/move, path restrictions, extension whitelist, SQLite history log, execute_naming_plan, execute_ingest

**Subagent D: Claude Code Plugin + Desktop Extension**
- Files: videodrome-plugin/**, manifest.json, docs/adr/**
- Tests: tests/test_safety_hook.py, tests/test_plugin_structure.py
- Scope: All 8 commands, 4 agents, safety hook, session hook, SKILL.md, .mcpb manifest, plugin.json, .mcp.json, ADRs

### Phase 3: Watcher (sequential, after Phase 2)
Depends on MediaMatcher (B), FileManager (C), IngestHistory (C), and PlexClient (A).
- Files: server/watcher.py
- Tests: tests/test_watcher.py
- Scope: watchdog Observer, stability check, async bridge, queue routing, rate limiting

### Phase 4: Server Integration (sequential, after Phase 3)
Wire everything together in server/main.py.
- Files: server/main.py
- Tests: Run full test suite
- Scope: FastMCP lifespan, tool registration, watcher lifecycle, env var config

## Component Details

### PlexClient (server/client.py)
Protocol-based client wrapping python-plexapi. Factory reads env vars (PLEX_URL, PLEX_TOKEN). Wraps synchronous plexapi calls with asyncio.to_thread().

### TMDb Cache (server/tmdb_cache.py)
SQLite-backed cache. Key: (title, year, media_type). TTL: 30 days. Auto-creates table on init.

### MediaMatcher (server/matcher.py)
Pipeline: guessit(filename) -> TMDb search (cached) -> confidence scoring -> Plex path construction.
Confidence: title similarity (40%), year match (30%), popularity (15%), type match (15%).

### FileManager (server/files.py)
Path restriction enforcement via PLEX_MEDIA_ROOT and PLEX_INGEST_DIR.
Extension whitelist: .mkv, .mp4, .avi, .m4v, .ts, .wmv, .mov

### IngestWatcher (server/watcher.py)
watchdog.Observer monitoring PLEX_INGEST_DIR. Stability check (60s stable size). High confidence auto-processes; low confidence queues for review. Bridges threads to asyncio via loop.call_soon_threadsafe().

### IngestHistory (server/history.py)
SQLite log: timestamp, source, destination, TMDb ID, confidence, status. Duplicate detection by TMDb ID.

## Verification
1. pytest tests/ -v - All tests pass
2. uv run server/main.py - MCP server starts without errors
3. Test batch identification with sample filenames
4. Verify TMDb cache stores and retrieves correctly
5. Test watcher: simulate file events, confirm queue routing
6. Verify safety hook blocks destructive tool calls
7. Install Claude Code plugin, test commands
8. Build .mcpb bundle, install in Claude Desktop
