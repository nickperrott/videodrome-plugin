#!/bin/bash
# Update Claude Desktop configuration for Videodrome

CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

echo "Updating Claude Desktop configuration..."
echo "Config file: $CONFIG_FILE"

# Create backup
cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
echo "✓ Backup created"

# Update the config using sed
sed -i '' 's|"plex":|"videodrome":|g' "$CONFIG_FILE"
sed -i '' 's|/Users/nick/git/plex-claude-plugin|/Users/nick/git/videodrome-plugin|g' "$CONFIG_FILE"
sed -i '' 's|/Users/nick/.config/plex-mcp/.env|/Users/nick/.config/videodrome/.env|g' "$CONFIG_FILE"
sed -i '' 's|"plex-mcp"|"videodrome"|g' "$CONFIG_FILE"

echo "✓ Configuration updated"
echo ""
echo "Next steps:"
echo "1. Restart Claude Desktop: killall Claude && open -a Claude"
echo "2. Verify 'videodrome' server appears in MCP servers list"
