#!/bin/bash
# Setup Plex MCP Server for installation from git repo

set -e

echo "Plex MCP Server Setup"
echo "====================="
echo

# Configuration
INSTALL_DIR="$HOME/git/videodrome-plugin"
CONFIG_DIR="$HOME/.config/videodrome"
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installation directories:"
echo "  Code:   $INSTALL_DIR"
echo "  Config: $CONFIG_DIR"
echo

# Step 1: Create config directory
echo "1. Creating config directory..."
mkdir -p "$CONFIG_DIR"
echo "   ✓ Created $CONFIG_DIR"

# Step 2: Copy .env file if it exists, or create from example
if [ -f "$REPO_DIR/.env" ]; then
    echo "2. Copying existing .env to config directory..."
    cp "$REPO_DIR/.env" "$CONFIG_DIR/.env"
    echo "   ✓ Copied .env to $CONFIG_DIR"
elif [ -f "$REPO_DIR/.env.example" ]; then
    echo "2. Creating .env from example..."
    cp "$REPO_DIR/.env.example" "$CONFIG_DIR/.env"
    echo "   ✓ Created $CONFIG_DIR/.env from example"
    echo "   ⚠️  Please edit with your credentials:"
    echo "      nano $CONFIG_DIR/.env"
else
    echo "2. Creating new .env file..."
    cat > "$CONFIG_DIR/.env" << 'EOF'
# Plex MCP Server Configuration

# Required Settings
PLEX_URL=https://plex.tv
PLEX_TOKEN=your-token-here
TMDB_API_KEY=your-api-key-here
PLEX_MEDIA_ROOT=/path/to/media

# Optional Settings
PLEX_INGEST_DIR=/path/to/downloads
PLEX_AUTO_INGEST=true
PLEX_CONFIDENCE_THRESHOLD=0.85
PLEX_WATCHER_AUTO_START=true
EOF
    echo "   ✓ Created $CONFIG_DIR/.env"
    echo "   ⚠️  Please edit with your credentials:"
    echo "      nano $CONFIG_DIR/.env"
fi

# Step 3: Clone/copy repo to install directory
if [ "$REPO_DIR" = "$INSTALL_DIR" ]; then
    echo "3. Already in install directory, skipping copy..."
else
    echo "3. Installing to $INSTALL_DIR..."
    if [ -d "$INSTALL_DIR" ]; then
        echo "   Directory exists, updating..."
        rsync -av --exclude='.git' --exclude='venv' --exclude='*.pyc' --exclude='__pycache__' --exclude='*.db' --exclude='*.db-*' --exclude='.env' "$REPO_DIR/" "$INSTALL_DIR/"
    else
        mkdir -p "$INSTALL_DIR"
        rsync -av --exclude='.git' --exclude='venv' --exclude='*.pyc' --exclude='__pycache__' --exclude='*.db' --exclude='*.db-*' --exclude='.env' "$REPO_DIR/" "$INSTALL_DIR/"
    fi
    echo "   ✓ Installed to $INSTALL_DIR"
fi

# Step 4: Install dependencies
echo "4. Installing Python dependencies..."
cd "$INSTALL_DIR"
if command -v uv &> /dev/null; then
    uv venv --quiet 2>/dev/null || true
    uv pip install -e . --quiet
    echo "   ✓ Installed with uv"
else
    python3 -m venv venv
    source venv/bin/activate
    pip install -e . --quiet
    echo "   ✓ Installed with pip"
fi

# Step 5: Update Claude Desktop config
echo "5. Updating Claude Desktop configuration..."
mkdir -p "$(dirname "$CLAUDE_CONFIG")"

python3 << EOF
import json
import os
from pathlib import Path

config_file = "$CLAUDE_CONFIG"
install_dir = "$INSTALL_DIR"

try:
    with open(config_file, 'r') as f:
        config = json.load(f)
except:
    config = {"mcpServers": {}}

if "mcpServers" not in config:
    config["mcpServers"] = {}

# Update or add plex server
config["mcpServers"]["plex"] = {
    "command": "uv",
    "args": [
        "run",
        "--directory",
        install_dir,
        "videodrome"
    ]
}

# Backup existing config
if os.path.exists(config_file):
    backup = f"{config_file}.backup"
    with open(config_file, 'r') as f:
        with open(backup, 'w') as b:
            b.write(f.read())

# Write new config
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print("   ✓ Updated Claude Desktop config")
print(f"   ✓ Backup saved to {config_file}.backup")
EOF

# Step 6: Create update script
echo "6. Creating update script..."
cat > "$INSTALL_DIR/update.sh" << 'UPDATEEOF'
#!/bin/bash
# Update Plex MCP Server

INSTALL_DIR="$HOME/git/videodrome-plugin"
cd "$INSTALL_DIR"

echo "Updating Plex MCP Server..."
git pull
uv pip install -e .
echo "✓ Updated successfully"
echo "Please restart Claude Desktop"
UPDATEEOF
chmod +x "$INSTALL_DIR/update.sh"
echo "   ✓ Created update script: $INSTALL_DIR/update.sh"

# Done!
echo
echo "✅ Installation complete!"
echo
echo "Configuration file: $CONFIG_DIR/.env"
echo "Installation: $INSTALL_DIR"
echo
echo "Next steps:"
echo "1. Edit config:  nano $CONFIG_DIR/.env"
echo "2. Test server:  cd $INSTALL_DIR && uv run videodrome"
echo "3. Restart Claude Desktop"
echo
echo "To update later: $INSTALL_DIR/update.sh"
echo
