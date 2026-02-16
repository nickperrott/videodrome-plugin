#!/bin/bash
# Install Plex MCP Server to Claude Desktop

CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
BACKUP_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json.backup-$(date +%Y%m%d-%H%M%S)"

echo "Installing Plex MCP Server to Claude Desktop..."
echo

# Backup existing config
if [ -f "$CONFIG_FILE" ]; then
    echo "Creating backup: $BACKUP_FILE"
    cp "$CONFIG_FILE" "$BACKUP_FILE"
fi

# Read current config
if [ -f "$CONFIG_FILE" ]; then
    CURRENT=$(cat "$CONFIG_FILE")
else
    CURRENT='{"mcpServers":{}}'
fi

# Add Plex server using Python
python3 << 'EOF'
import json
import sys

config_file = sys.argv[1]
try:
    with open(config_file, 'r') as f:
        config = json.load(f)
except:
    config = {"mcpServers": {}}

if "mcpServers" not in config:
    config["mcpServers"] = {}

config["mcpServers"]["plex"] = {
    "command": "uv",
    "args": [
        "run",
        "--directory",
        "/Users/nick/conductor/workspaces/videodrome-plugin/montreal-v1",
        "--env-file",
        "/Users/nick/conductor/workspaces/videodrome-plugin/montreal-v1/.env",
        "videodrome"
    ]
}

with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print("✅ Plex MCP Server added to Claude Desktop config")
print("")
print("Configuration:")
print(json.dumps(config["mcpServers"]["plex"], indent=2))
EOF
python3 -c "
import json
config_file = '$CONFIG_FILE'
with open(config_file, 'r') as f:
    config = json.load(f)
if 'mcpServers' not in config:
    config['mcpServers'] = {}
config['mcpServers']['plex'] = {
    'command': 'uv',
    'args': [
        'run',
        '--directory',
        '/Users/nick/conductor/workspaces/videodrome-plugin/montreal-v1',
        '--env-file',
        '/Users/nick/conductor/workspaces/videodrome-plugin/montreal-v1/.env',
        'videodrome'
    ]
}
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)
print('✅ Plex MCP Server added to Claude Desktop config')
" "$CONFIG_FILE"

echo
echo "Next steps:"
echo "1. Restart Claude Desktop"
echo "2. The Plex MCP tools will be automatically available"
echo
echo "To verify, you can check the config:"
echo "cat '$CONFIG_FILE'"
