# Installation Guide

Three ways to install the Plex MCP Server:

## Option 1: From Bundle (.mcpb) - Easiest for Distribution

1. **Build the bundle:**
   ```bash
   cd /path/to/videodrome-plugin/montreal-v1
   chmod +x build_bundle.py
   ./build_bundle.py
   ```

2. **Distribute `videodrome-0.1.0.mcpb`** to users

3. **Users install:**
   ```bash
   # Extract and run installer
   unzip videodrome-0.1.0.mcpb
   bash install.sh

   # Configure
   nano ~/git/videodrome-plugin/.env

   # Restart Claude Desktop
   ```

## Option 2: From GitHub - Best for Development

1. **Install directly from repo:**
   ```bash
   # Install to standard location
   INSTALL_DIR="$HOME/git/videodrome-plugin"
   git clone https://github.com/yourusername/videodrome-plugin.git "$INSTALL_DIR"
   cd "$INSTALL_DIR"

   # Setup environment
   uv venv
   uv pip install -e .

   # Configure
   cp .env.example .env
   nano .env
   ```

2. **Add to Claude Desktop config:**
   ```bash
   # Edit config
   nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

   Add this server:
   ```json
   {
     "mcpServers": {
       "plex": {
         "command": "uv",
         "args": [
           "run",
           "--directory",
           "/Users/yourusername/git/videodrome-plugin",
           "--env-file",
           "/Users/yourusername/git/videodrome-plugin/.env",
           "videodrome"
         ]
       }
     }
   }
   ```

3. **Restart Claude Desktop**

## Option 3: System-wide with pipx - For Power Users

1. **Install with pipx:**
   ```bash
   # From GitHub
   pipx install git+https://github.com/yourusername/videodrome-plugin.git

   # Or from local path
   pipx install /path/to/videodrome-plugin
   ```

2. **Configure:**
   ```bash
   mkdir -p ~/.config/videodrome
   cat > ~/.config/videodrome/.env << 'EOF'
   PLEX_URL=https://plex.tv
   PLEX_TOKEN=your-token-here
   TMDB_API_KEY=your-api-key-here
   PLEX_MEDIA_ROOT=/path/to/media
   EOF
   ```

3. **Add to Claude Desktop config:**
   ```json
   {
     "mcpServers": {
       "plex": {
         "command": "videodrome",
         "env": {
           "PLEX_URL": "https://plex.tv",
           "PLEX_TOKEN": "your-token-here",
           "TMDB_API_KEY": "your-api-key-here",
           "PLEX_MEDIA_ROOT": "/path/to/media"
         }
       }
     }
   }
   ```

## Configuration

All methods require these environment variables:

```bash
# Required
PLEX_URL=https://plex.tv              # Or http://your-server-ip:32400
PLEX_TOKEN=your-plex-token            # Get from browser localStorage
TMDB_API_KEY=your-tmdb-api-key        # From https://www.themoviedb.org/settings/api
PLEX_MEDIA_ROOT=/Volumes/MEDIA        # Root path for media files

# Optional
PLEX_INGEST_DIR=/path/to/downloads    # Folder to watch for new media
PLEX_AUTO_INGEST=true                 # Auto-process high-confidence matches
PLEX_CONFIDENCE_THRESHOLD=0.85        # Minimum confidence for auto-ingest
PLEX_WATCHER_AUTO_START=true          # Start file watcher on server start
```

See [QUICKSTART.md](QUICKSTART.md) for detailed configuration instructions.

## Updating

### Bundle installation:
```bash
# Download new bundle
unzip -o videodrome-0.1.1.mcpb -d ~/git/videodrome-plugin
cd ~/git/videodrome-plugin
uv pip install -e .
```

### Git installation:
```bash
cd ~/git/videodrome-plugin
git pull
uv pip install -e .
```

### pipx installation:
```bash
pipx upgrade videodrome-plugin
```

## Troubleshooting

**MCP server not appearing in Claude Desktop:**
1. Check config file syntax: `cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | python3 -m json.tool`
2. Check server runs manually: `cd ~/git/videodrome-plugin && uv run --env-file .env videodrome`
3. Check Claude Desktop logs: `~/Library/Logs/Claude/`

**Connection errors:**
1. Test token: `curl -H "X-Plex-Token: YOUR_TOKEN" https://plex.tv/pms/servers.xml`
2. Check .env file exists and has correct values
3. See [QUICKSTART.md](QUICKSTART.md) for token retrieval instructions

**Import errors:**
1. Reinstall dependencies: `cd ~/git/videodrome-plugin && uv pip install -e .`
2. Check Python version: `python3 --version` (requires >=3.11)
