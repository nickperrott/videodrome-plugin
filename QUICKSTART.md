# Plex MCP Server - Quick Start Guide

Get your Plex MCP server running in 5 minutes!

## Prerequisites

- Python 3.11+ with `uv` installed
- A running Plex Media Server
- A TMDb account (free)

## Step 1: Get Your Plex Token

Your Plex token is needed for API authentication.

### Method 1: Via Plex Web (Easiest)

1. Open Plex Web App: `http://YOUR_PLEX_IP:32400/web`
2. Play any media item
3. Click the ⋯ (three dots) menu → "Get Info"
4. Click "View XML"
5. Look in the URL bar for `X-Plex-Token=XXXXX`
6. Copy the token after the `=` sign

### Method 2: Via Settings

1. Sign in to Plex Web
2. Settings → Account → scroll down
3. Look for your authentication token in the page source (Ctrl+U / Cmd+Option+U)
4. Search for `authToken` or `X-Plex-Token`

**Official Guide**: https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/

## Step 2: Get Your TMDb API Key

TMDb provides movie/TV metadata for file identification.

1. Create a free account at https://www.themoviedb.org/signup
2. Go to Settings → API: https://www.themoviedb.org/settings/api
3. Request an API key (select "Developer" for free use)
4. Copy your "API Key (v3 auth)"

## Step 3: Find Your Plex Server URL

Your Plex server URL is typically:
- **Local**: `http://192.168.1.XXX:32400` (find your local IP)
- **Localhost**: `http://localhost:32400` (if running on same machine)
- **Remote**: `http://YOUR_PUBLIC_IP:32400` or `https://YOUR_DOMAIN:32400`

To find your local IP:
```bash
# macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# or
hostname -I
```

## Step 4: Configure Environment Variables

### Option A: Use the Interactive Configure Command (Recommended)

```bash
cd /path/to/videodrome-plugin/montreal-v1
uv run python -c "from plex_plugin.hooks.configure import configure; configure()"
```

This will:
- Prompt you for each value
- Validate your inputs
- Test the connection
- Save to `.env` file

### Option B: Manual Configuration

Create a `.env` file in the project root:

```bash
cd /path/to/videodrome-plugin/montreal-v1
cat > .env << 'EOF'
# Required
PLEX_URL=http://192.168.1.100:32400
PLEX_TOKEN=your-plex-token-here
TMDB_API_KEY=your-tmdb-api-key-here
PLEX_MEDIA_ROOT=/path/to/your/media

# Optional - for auto-ingestion features
PLEX_INGEST_DIR=/path/to/ingest/folder
PLEX_AUTO_INGEST=false
PLEX_CONFIDENCE_THRESHOLD=0.85
PLEX_WATCHER_AUTO_START=false
EOF
```

### Option C: Export in Shell

```bash
export PLEX_URL=http://192.168.1.100:32400
export PLEX_TOKEN=your-plex-token-here
export TMDB_API_KEY=your-tmdb-api-key-here
export PLEX_MEDIA_ROOT=/path/to/your/media
```

## Step 5: Test the Server

```bash
# Load .env file and run server
uv run --env-file .env videodrome

# Or if you exported variables
uv run videodrome
```

You should see:
```
2026-02-10 12:54:27 - server.main - INFO - Starting Plex MCP Server...
2026-02-10 12:54:27 - server.main - INFO - Connecting to Plex server at http://...
2026-02-10 12:54:28 - server.main - INFO - Initializing TMDb cache...
2026-02-10 12:54:28 - server.main - INFO - Plex MCP Server started successfully!
```

## Step 6: Connect to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "plex": {
      "command": "uv",
      "args": [
        "--directory",
        "/FULL/PATH/TO/videodrome-plugin/montreal-v1",
        "run",
        "--env-file",
        ".env",
        "videodrome"
      ]
    }
  }
}
```

**Important**: Use absolute paths, not `~` or relative paths!

Restart Claude Desktop and you should see the Plex server connected! 🎉

## Step 7: Test with Claude Code Plugin

If using Claude Code, install the plugin:

```bash
# From the project directory
claude plugin install videodrome-plugin
```

Then use commands like:
- `/videodrome:status` - Check server status
- `/videodrome:identify` - Identify a media file
- `/videodrome:scan` - Trigger a library scan

## Configuration Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PLEX_URL` | Plex server URL | `http://192.168.1.100:32400` |
| `PLEX_TOKEN` | X-Plex-Token for auth | `abc123def456...` |
| `TMDB_API_KEY` | TMDb API key | `xyz789uvw123...` |
| `PLEX_MEDIA_ROOT` | Root path for media | `/data/media` or `/Volumes/Media` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLEX_INGEST_DIR` | (none) | Folder to watch for new files |
| `PLEX_AUTO_INGEST` | `false` | Auto-process high-confidence matches |
| `PLEX_CONFIDENCE_THRESHOLD` | `0.85` | Minimum confidence for auto-ingest (0.0-1.0) |
| `PLEX_WATCHER_AUTO_START` | `false` | Start file watcher on server launch |

## Troubleshooting

### "Connection refused" or "Unable to connect"

- **Check Plex is running**: Open `http://YOUR_IP:32400/web` in browser
- **Check firewall**: Ensure port 32400 is accessible
- **Try localhost**: If on same machine, use `http://localhost:32400`

### "Unauthorized" or "Invalid token"

- **Regenerate token**: Get a fresh token from Plex Web
- **Check token format**: Should be a long alphanumeric string (no spaces)

### "TMDb API error"

- **Verify API key**: Test at https://api.themoviedb.org/3/movie/550?api_key=YOUR_KEY
- **Check rate limits**: Free tier has rate limits
- **Wait and retry**: TMDb occasionally has outages

### "Path does not exist"

- **Check PLEX_MEDIA_ROOT**: Must be an absolute path
- **Check permissions**: Server must have read access
- **Use correct separators**:
  - macOS/Linux: `/Volumes/Media` or `/mnt/media`
  - Windows: `C:\Media` or `//server/Media`

### Server won't start

```bash
# Check environment variables are set
env | grep PLEX
env | grep TMDB

# Try running with debug output
uv run --env-file .env videodrome 2>&1 | tee server.log
```

## Examples

### Minimal .env for Testing

```bash
PLEX_URL=http://localhost:32400
PLEX_TOKEN=abc123...
TMDB_API_KEY=xyz789...
PLEX_MEDIA_ROOT=/tmp/media
```

### Full .env for Production

```bash
# Plex Connection
PLEX_URL=http://192.168.1.100:32400
PLEX_TOKEN=abc123def456ghi789...
TMDB_API_KEY=xyz789uvw456rst123...

# Media Paths
PLEX_MEDIA_ROOT=/Volumes/MediaLibrary
PLEX_INGEST_DIR=/Volumes/MediaLibrary/Incoming

# Auto-Ingest Settings
PLEX_AUTO_INGEST=true
PLEX_CONFIDENCE_THRESHOLD=0.90
PLEX_WATCHER_AUTO_START=true
```

## Next Steps

Once configured:

1. **Test basic operations**: Use `/videodrome:status` to verify connection
2. **Identify media files**: Use `/videodrome:identify` on sample files
3. **Set up auto-ingest**: Configure watcher for automated processing
4. **Explore commands**: Try all 8 plugin commands

---

**Need help?** Check the [README.md](README.md) for full documentation or open an issue on GitHub.
