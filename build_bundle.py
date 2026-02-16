#!/usr/bin/env python3
"""
Build an MCP bundle (.mcpb) for distribution.

An .mcpb file is a zip archive containing:
- server/ directory with all Python code
- videodrome-plugin/ directory with plugin metadata
- pyproject.toml for dependencies
- README.md and other docs
"""

import zipfile
import os
from pathlib import Path
import json

def build_bundle():
    """Build the .mcpb bundle file."""

    bundle_name = "videodrome-0.1.0.mcpb"
    base_dir = Path(__file__).parent

    # Files to include
    include_patterns = [
        "server/**/*.py",
        "videodrome-plugin/**/*",
        "pyproject.toml",
        "README.md",
        "QUICKSTART.md",
        "LICENSE",
        ".env.example",
    ]

    # Files to exclude
    exclude_patterns = [
        "**/__pycache__/**",
        "**/*.pyc",
        "**/.pytest_cache/**",
        "**/venv/**",
        "**/.env",
        "**/tests/**",
        "**/*.db",
        "**/*.db-*",
    ]

    print(f"Building MCP bundle: {bundle_name}")
    print()

    # Create .env.example if it doesn't exist
    env_example = base_dir / ".env.example"
    if not env_example.exists():
        env_example.write_text("""# Plex MCP Server Configuration

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
""")
        print("✓ Created .env.example")

    # Create the bundle
    with zipfile.ZipFile(bundle_name, 'w', zipfile.ZIP_DEFLATED) as bundle:
        files_added = 0

        # Add all Python files from server/
        for py_file in (base_dir / "server").rglob("*.py"):
            if "__pycache__" not in str(py_file):
                arcname = py_file.relative_to(base_dir)
                bundle.write(py_file, arcname)
                files_added += 1
                print(f"  + {arcname}")

        # Add plugin files
        for plugin_file in (base_dir / "videodrome-plugin").rglob("*"):
            if plugin_file.is_file() and "__pycache__" not in str(plugin_file):
                arcname = plugin_file.relative_to(base_dir)
                bundle.write(plugin_file, arcname)
                files_added += 1
                print(f"  + {arcname}")

        # Add project files
        for filename in ["pyproject.toml", "README.md", "QUICKSTART.md", ".env.example"]:
            filepath = base_dir / filename
            if filepath.exists():
                bundle.write(filepath, filename)
                files_added += 1
                print(f"  + {filename}")

        # Add LICENSE if exists
        license_file = base_dir / "LICENSE"
        if license_file.exists():
            bundle.write(license_file, "LICENSE")
            files_added += 1
            print(f"  + LICENSE")

        # Add install script
        install_script = """#!/bin/bash
# Plex MCP Installation Script

INSTALL_DIR="$HOME/.local/share/videodrome"
CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

echo "Installing Plex MCP Server..."
echo

# Extract bundle
mkdir -p "$INSTALL_DIR"
unzip -q videodrome-*.mcpb -d "$INSTALL_DIR"

# Setup virtual environment
cd "$INSTALL_DIR"
uv venv
uv pip install -e .

# Configure
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo "⚠️  Please edit $INSTALL_DIR/.env with your credentials"
    echo "   Run: nano $INSTALL_DIR/.env"
fi

# Add to Claude Desktop config
python3 << 'EOF'
import json
import os

config_file = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
install_dir = os.path.expanduser("~/.local/share/videodrome")

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
        install_dir,
        "--env-file",
        f"{install_dir}/.env",
        "videodrome"
    ]
}

os.makedirs(os.path.dirname(config_file), exist_ok=True)
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print("✅ Plex MCP Server installed!")
EOF

echo
echo "Installation complete!"
echo "1. Edit config: nano $INSTALL_DIR/.env"
echo "2. Restart Claude Desktop"
"""
        bundle.writestr("install.sh", install_script)
        files_added += 1
        print(f"  + install.sh")

    print()
    print(f"✅ Bundle created: {bundle_name}")
    print(f"   Files: {files_added}")
    print(f"   Size: {os.path.getsize(bundle_name) / 1024:.1f} KB")
    print()
    print("Distribution:")
    print(f"  1. Share {bundle_name} file")
    print(f"  2. Users run: unzip {bundle_name} && bash install.sh")
    print()

if __name__ == "__main__":
    build_bundle()
