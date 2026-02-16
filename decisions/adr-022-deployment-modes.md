# ADR-022: Operational Deployment Modes

**Status:** Accepted
**Date:** 2026-02-16
**Deciders:** System Architect
**Related:** ADR-021 (Transmission Integration)

---

## Context

The Plex MCP plugin provides automation features including:
- File system watching for new downloads
- Automatic media identification and classification
- TMDb metadata matching
- Duplicate detection
- Automated ingestion to Plex libraries
- (Future) Transmission torrent monitoring and completion detection

**Key Question:** How should the automation services be deployed and operated?

### Current Architecture: MCP Server Model

The plugin runs as an **MCP (Model Context Protocol) server** that:
- Starts when an MCP client connects to it
- Initializes watchers and background tasks during startup
- Runs asyncio event loops for polling/monitoring
- Stops when the MCP client disconnects

**Implications:**
- ✅ Zero configuration - works out of the box
- ✅ Integrated with MCP client workflow
- ✅ Easy debugging via MCP client logs
- ❌ Only runs while an MCP client is active
- ❌ Stops when the MCP client closes
- ❌ Does not auto-start on system boot

---

## Decision

**Accept the MCP-only operational mode as the initial deployment strategy**, with clear documentation of alternative deployment options for future consideration.

### Rationale

1. **Simplicity First:** MCP-only mode requires zero additional setup or configuration
2. **Development Focus:** Allows focus on core functionality rather than daemon management
3. **User Control:** User explicitly controls when automation is active (MCP client connected = automation on)
4. **Iterative Approach:** Can add daemon mode later if 24/7 operation is needed
5. **Debugging:** Easier to develop and debug when integrated with an MCP client

### Accepted Tradeoffs

**What We Accept:**
- Automation only runs while an MCP client is active
- No processing during machine restarts or when no MCP client is connected
- Completed torrents may sit unprocessed until the next MCP client session

**What We Gain:**
- Simple deployment (no system service configuration)
- Integrated logging and debugging
- Clear operational state (MCP client connected = automation active)
- Easy to disable (disconnect MCP client)

---

## Alternative Deployment Modes (Documented for Future)

### Option 1: MCP Server Only (CURRENT - ACCEPTED)

**Architecture:**
```
MCP Client Running
    ↓
MCP Server Active
    ↓
Watcher Polling (filesystem + Transmission)
    ↓
Auto-ingest on completion
```

**Lifecycle:**
- Start: When an MCP client connects to MCP server
- Stop: When MCP client disconnects
- Restart: Manual (reconnect MCP client)

**Configuration:**
```bash
# ~/.config/plex-mcp/.env
PLEX_WATCHER_AUTO_START=true  # Start watcher when MCP server starts
PLEX_AUTO_INGEST=true
TRANSMISSION_POLL_INTERVAL=30
```

**Management:**
- Status: Check MCP client connection
- Logs: MCP server logs (via MCP client)
- Control: Connect/disconnect MCP client

**Use Case:**
- Interactive media management
- Development and testing
- Users who actively manage their media library

---

### Option 2: Standalone Daemon Mode (FUTURE)

**Architecture:**
```
System Boot
    ↓
launchd starts daemon
    ↓
Daemon polls Transmission + filesystem 24/7
    ↓
Auto-ingest to Plex
    ↓
MCP server provides management interface (optional)
```

**Implementation:**

**File:** `server/daemon.py`
```python
#!/usr/bin/env python3
"""
Standalone daemon mode for 24/7 operation.
Runs independently of any MCP client.
"""

import os
import asyncio
import signal
import logging
from pathlib import Path

from server.watcher import IngestWatcher
from server.transmission import TransmissionClient
from server.matcher import MediaMatcher
from server.files import FileManager
from server.history import IngestHistory
from server.tmdb_cache import TMDbCache

logger = logging.getLogger(__name__)


def load_config() -> Path | None:
    """Load configuration from ~/.config/plex-mcp/.env or current directory."""
    config_dir = Path.home() / ".config" / "plex-mcp"
    config_file = config_dir / ".env"
    env_path = config_file if config_file.exists() else Path.cwd() / ".env"

    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    if key and value:
                        os.environ.setdefault(key.strip(), value.strip())
        return env_path

    return None


class PlexDaemon:
    """Standalone daemon for 24/7 media ingestion."""

    def __init__(self):
        self.watcher = None
        self.transmission = None
        self.running = False

    async def start(self):
        """Initialize and start all services."""
        logger.info("Starting Plex MCP Daemon...")

        # Initialize all components (same as MCP server)
        # ... (initialization code)

        # Start watcher
        await self.watcher.start()
        logger.info("Watcher started")

        # Start Transmission monitoring if configured
        if self.transmission:
            await self.transmission.start_monitoring()
            logger.info("Transmission monitoring started")

        self.running = True
        logger.info("Daemon running - Press Ctrl+C to stop")

    async def stop(self):
        """Gracefully stop all services."""
        logger.info("Stopping Plex MCP Daemon...")

        if self.watcher:
            await self.watcher.stop()

        if self.transmission:
            await self.transmission.stop_monitoring()

        self.running = False
        logger.info("Daemon stopped")

    async def run(self):
        """Main daemon loop."""
        await self.start()

        # Block until interrupted
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    raise KeyboardInterrupt


async def main():
    """Entry point for daemon mode."""
    env_path = load_config()
    if env_path:
        logger.info(f"Loaded configuration from: {env_path}")
    else:
        logger.warning("No .env file found. Using process environment only.")

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    daemon = PlexDaemon()
    await daemon.run()


if __name__ == "__main__":
    asyncio.run(main())
```

**File:** `~/Library/LaunchAgents/com.plex.mcp.daemon.plist`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.plex.mcp.daemon</string>

    <key>ProgramArguments</key>
    <array>
        <string>/path/to/plex-mcp/.venv/bin/python</string>
        <string>/path/to/plex-mcp/server/daemon.py</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/nick/.local/share/plex-mcp/daemon.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/nick/.local/share/plex-mcp/daemon.error.log</string>

    <key>WorkingDirectory</key>
    <string>/path/to/plex-mcp</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/path/to/plex-mcp</string>
    </dict>
</dict>
</plist>
```

**Configuration:**
```bash
# ~/.config/plex-mcp/.env
PLEX_MODE=daemon  # Enable daemon mode

# Daemon-specific settings
DAEMON_LOG_LEVEL=INFO
DAEMON_PID_FILE=/Users/nick/.local/share/plex-mcp/daemon.pid
```

**Management:**
```bash
# Load and start daemon (runs at boot)
launchctl load ~/Library/LaunchAgents/com.plex.mcp.daemon.plist

# Stop daemon
launchctl unload ~/Library/LaunchAgents/com.plex.mcp.daemon.plist

# Check status
launchctl list | grep com.plex.mcp.daemon

# View logs
tail -f ~/.local/share/plex-mcp/daemon.log

# Restart after changes
launchctl unload ~/Library/LaunchAgents/com.plex.mcp.daemon.plist
launchctl load ~/Library/LaunchAgents/com.plex.mcp.daemon.plist
```

**Use Case:**
- 24/7 automated media server
- Hands-off operation
- Production deployments
- Users who want "set it and forget it"

**Pros:**
- ✅ Runs 24/7, survives restarts
- ✅ Auto-starts on boot
- ✅ Independent of MCP clients
- ✅ Processes downloads immediately

**Cons:**
- ⚠️ Requires launchd configuration
- ⚠️ More complex to debug
- ⚠️ Separate process management
- ⚠️ Needs monitoring/alerting

---

### Option 3: Hybrid Mode (FUTURE)

**Architecture:**
```
┌─────────────────────────────────────────┐
│  Lightweight Daemon (24/7)              │
│  ─────────────────────────────────────  │
│  • Transmission monitoring              │
│  • High-confidence auto-ingest          │
│  • Queue low-confidence items           │
│  • Minimal dependencies                 │
└─────────────────┬───────────────────────┘
                  │
                  │ Shared SQLite Queue
                  │
┌─────────────────▼───────────────────────┐
│  MCP Server (On-Demand)                 │
│  ─────────────────────────────────────  │
│  • Review pending queue                 │
│  • Manual torrent management            │
│  • Library scanning                     │
│  • Statistics/history                   │
└─────────────────────────────────────────┘
```

**Shared State:**
- SQLite database for pending queue
- SQLite database for ingest history
- TMDb cache (optional - can be daemon-only)

**Daemon Responsibilities:**
- Poll Transmission for completions (every 30s)
- Identify media using MediaMatcher
- Auto-ingest if confidence >= threshold
- Queue for review if confidence < threshold
- Log all operations to history

**MCP Server Responsibilities:**
- Display pending queue
- Approve/reject queued items
- Manual torrent operations
- Library management
- View statistics and history

**Use Case:**
- Best of both worlds
- 24/7 automation for easy cases
- Interactive review for edge cases
- Production with manual oversight

**Pros:**
- ✅ 24/7 automated operation
- ✅ Manual control when needed
- ✅ Queue bridges daemon ↔ MCP
- ✅ Graceful degradation (daemon works alone)

**Cons:**
- ⚠️ Most complex architecture
- ⚠️ Two processes to manage
- ⚠️ Shared state coordination

---

### Option 4: Transmission Script Trigger (FUTURE)

**Architecture:**
```
Torrent Completes
    ↓
Transmission calls script
    ↓
Script triggers processing (via HTTP or direct)
    ↓
Media identified and ingested
```

**Implementation:**

**Transmission Configuration:**
```bash
# Set completion script in Transmission settings
transmission-remote --script-torrent-done-filename \
  /path/to/plex-mcp/scripts/on-torrent-complete.sh
```

**Script:** `scripts/on-torrent-complete.sh`
```bash
#!/bin/bash
# Called by Transmission when torrent completes
# Environment variables provided:
# - TR_TORRENT_DIR: Download directory
# - TR_TORRENT_NAME: Torrent name
# - TR_TORRENT_HASH: Info hash

LOG_FILE="$HOME/.local/share/plex-mcp/completion-hook.log"

echo "[$(date)] Torrent completed: $TR_TORRENT_NAME" >> "$LOG_FILE"

# Option A: Trigger standalone processing script
python3 /path/to/plex-mcp/scripts/process_torrent.py \
  --path "$TR_TORRENT_DIR/$TR_TORRENT_NAME" \
  --hash "$TR_TORRENT_HASH" \
  >> "$LOG_FILE" 2>&1

# Option B: Trigger MCP server via HTTP (if running)
# curl -X POST http://localhost:8080/api/process-torrent \
#   -H "Content-Type: application/json" \
#   -d "{\"path\": \"$TR_TORRENT_DIR/$TR_TORRENT_NAME\", \"hash\": \"$TR_TORRENT_HASH\"}"
```

**Use Case:**
- Immediate processing (no polling delay)
- Minimal background processes
- Transmission-centric workflow

**Pros:**
- ✅ Immediate notification (no 30s poll delay)
- ✅ No background daemon needed
- ✅ Event-driven (efficient)

**Cons:**
- ⚠️ Transmission-specific configuration
- ⚠️ Requires script execution permissions
- ⚠️ Harder to debug script failures
- ⚠️ Not portable (needs reconfiguration per machine)

---

## Migration Path (Future)

If 24/7 operation becomes needed, the migration path is:

### Phase 1: Extract Daemon Logic
1. Create `server/daemon.py` with standalone runner
2. Extract watcher initialization from `server/main.py` to shared module
3. Add daemon-specific configuration options

### Phase 2: Test Daemon Mode
1. Run daemon manually: `python3 server/daemon.py`
2. Verify watcher operates correctly
3. Verify Transmission monitoring works
4. Check SQLite queue persistence

### Phase 3: Create launchd Service
1. Create plist file in `~/Library/LaunchAgents/`
2. Load service: `launchctl load ...`
3. Verify auto-start on boot
4. Monitor logs for stability

### Phase 4: Hybrid Operation (Optional)
1. Run daemon for 24/7 automation
2. Use MCP server for manual review
3. Both processes share SQLite databases
4. Queue items bridge daemon → MCP

---

## Current Implementation Plan (MCP-Only)

Given the decision to start with MCP-only mode:

### Configuration
```bash
# ~/.config/plex-mcp/.env

# Watcher settings
PLEX_WATCHER_AUTO_START=true  # Start watcher when MCP connects
PLEX_AUTO_INGEST=true
PLEX_CONFIDENCE_THRESHOLD=0.85

# Transmission settings (per ADR-021)
TRANSMISSION_URL=http://localhost:9091/transmission/rpc
TRANSMISSION_POLL_INTERVAL=30
TRANSMISSION_AUTO_REMOVE=false
```

### Operational Notes

**When is automation active?**
- When an MCP client is running and connected to Plex MCP server
- Watcher auto-starts if `PLEX_WATCHER_AUTO_START=true`

**How to check status?**
```python
# Via an MCP client, call:
get_watcher_status()  # Returns running/stopped, queue size, etc.
```

**How to manually process completed torrents?**
1. Open an MCP client (for example, Claude Desktop or Claude Code)
2. MCP server connects
3. Watcher auto-starts and polls Transmission
4. OR manually call: `list_torrents()` and `approve_pending()`

**What happens when the MCP client closes?**
- MCP server stops
- Watcher stops
- Polling stops
- Torrents continue downloading (Transmission is independent)
- Processing resumes next time an MCP client starts

**What happens on system restart?**
- Transmission auto-starts (if configured in System Preferences)
- Plex server auto-starts (if configured)
- Plex MCP watcher: Does NOT auto-start
- Must open an MCP client to resume automation

---

## Documentation Requirements

### User-Facing Documentation

**README.md should include:**

```markdown
## Operation Modes

### Current: MCP Server Mode (Default)

The Plex MCP plugin runs as an MCP server that operates while an MCP client is active.

**Requirements:**
- MCP client running (Claude Desktop or Claude Code)
- MCP server connected

**Automation Features:**
- ✅ Watches ingest directory for new files
- ✅ Monitors Transmission for completed torrents
- ✅ Auto-identifies media via TMDb
- ✅ Auto-ingests high-confidence matches
- ✅ Queues low-confidence matches for review

**Limitations:**
- ⚠️ Only runs while an MCP client is active
- ⚠️ Does not auto-start on system boot
- ⚠️ Stops when the MCP client closes

**To enable automation:**
1. Open an MCP client
2. Automation starts automatically if `PLEX_WATCHER_AUTO_START=true`
3. Check status: Call `get_watcher_status()` tool

**Future:** 24/7 daemon mode is planned (see ADR-022) but not yet implemented.
```

---

## Success Criteria

**For MCP-Only Mode (Current):**
- ✅ Watcher starts when an MCP client connects (if auto-start enabled)
- ✅ Watcher stops when MCP client disconnects
- ✅ User can check watcher status via MCP tools
- ✅ User can manually start/stop watcher via MCP tools
- ✅ Documentation clearly explains operational model
- ✅ No unexpected background processes

**For Future Daemon Mode:**
- ⬜ Daemon runs independently of MCP clients
- ⬜ Auto-starts on system boot
- ⬜ Survives MCP client restarts
- ⬜ Logs to dedicated daemon log file
- ⬜ Manageable via launchctl

---

## References

- [MCP Server Lifecycle](https://modelcontextprotocol.io/docs/concepts/lifecycle)
- [macOS launchd Documentation](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [Transmission Script Execution](https://github.com/transmission/transmission/blob/main/docs/Editing-Configuration-Files.md#scripts)
- ADR-021: Transmission Integration

---

## Notes

This ADR documents the architectural decision to **start simple** with MCP-only mode, while preserving the option to add 24/7 daemon mode later if needed.

The key insight is that **most development and testing work happens with an MCP client open anyway**, so MCP-only mode provides sufficient automation for the initial implementation. If true 24/7 operation is needed in production, the migration path is well-defined and can be implemented incrementally.
