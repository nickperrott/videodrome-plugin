#!/usr/bin/env python3
"""Interactive configuration helper for Plex MCP Server.

This script helps you set up the required environment variables
for the Plex MCP server with validation and connection testing.
"""

import sys
import os
from pathlib import Path
from typing import Optional, Dict, Tuple


def print_header():
    """Print welcome header."""
    print("=" * 70)
    print("🎬 Plex MCP Server - Interactive Configuration")
    print("=" * 70)
    print()


def print_section(title: str):
    """Print section header."""
    print()
    print("-" * 70)
    print(f"  {title}")
    print("-" * 70)
    print()


def prompt_with_default(prompt: str, default: Optional[str] = None, required: bool = True) -> str:
    """Prompt user for input with optional default value."""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "

    while True:
        value = input(full_prompt).strip()

        if not value and default:
            return default

        if not value and required:
            print("❌ This field is required. Please enter a value.")
            continue

        return value


def prompt_yes_no(prompt: str, default: bool = False) -> bool:
    """Prompt user for yes/no confirmation."""
    default_str = "Y/n" if default else "y/N"
    full_prompt = f"{prompt} [{default_str}]: "

    while True:
        value = input(full_prompt).strip().lower()

        if not value:
            return default

        if value in ['y', 'yes']:
            return True
        elif value in ['n', 'no']:
            return False
        else:
            print("❌ Please enter 'y' or 'n'")


def validate_url(url: str) -> Tuple[bool, str]:
    """Validate Plex URL format."""
    if not url:
        return False, "URL cannot be empty"

    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "URL must start with http:// or https://"

    if ":32400" not in url:
        print("⚠️  Warning: Plex typically runs on port 32400. Is this intentional?")

    return True, "OK"


def validate_path(path: str, must_exist: bool = True) -> Tuple[bool, str]:
    """Validate filesystem path."""
    if not path:
        return False, "Path cannot be empty"

    path_obj = Path(path).expanduser()

    if must_exist and not path_obj.exists():
        return False, f"Path does not exist: {path}"

    if not path_obj.is_absolute():
        return False, "Path must be absolute (start with / or C:\\)"

    return True, "OK"


def test_plex_connection(url: str, token: str) -> bool:
    """Test connection to Plex server."""
    print("\n🔄 Testing connection to Plex server...")

    try:
        # Try importing plexapi
        try:
            from plexapi.server import PlexServer
        except ImportError:
            print("⚠️  plexapi not installed - skipping connection test")
            print("   Install with: uv pip install plexapi")
            return True

        # Try connecting
        server = PlexServer(url, token, timeout=10)
        print(f"✅ Connected successfully to: {server.friendlyName}")
        print(f"   Version: {server.version}")
        print(f"   Platform: {server.platform}")
        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n   Troubleshooting:")
        print("   1. Check that Plex is running")
        print("   2. Verify the URL (try http://localhost:32400 if local)")
        print("   3. Verify your Plex token is correct")
        print("   4. Check firewall settings")
        return False


def test_tmdb_api(api_key: str) -> bool:
    """Test TMDb API key."""
    print("\n🔄 Testing TMDb API key...")

    try:
        import requests
    except ImportError:
        print("⚠️  requests not installed - skipping API test")
        return True

    try:
        # Test API with a simple movie lookup
        url = f"https://api.themoviedb.org/3/movie/550?api_key={api_key}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ TMDb API working! Test result: {data.get('title', 'Unknown')}")
            return True
        elif response.status_code == 401:
            print("❌ Invalid API key")
            return False
        else:
            print(f"❌ API error: {response.status_code}")
            return False

    except Exception as e:
        print(f"⚠️  Could not test TMDb API: {e}")
        return True  # Don't fail on network issues


def save_env_file(config: Dict[str, str], file_path: Path) -> bool:
    """Save configuration to .env file."""
    print(f"\n💾 Saving configuration to {file_path}...")

    try:
        # Backup existing .env if it exists
        if file_path.exists():
            backup_path = file_path.with_suffix(".env.backup")
            file_path.rename(backup_path)
            print(f"   📦 Backed up existing config to {backup_path}")

        # Write new .env file
        with open(file_path, 'w') as f:
            f.write("# Plex MCP Server Configuration\n")
            f.write("# Generated by configure.py\n\n")

            f.write("# Required Settings\n")
            for key in ["PLEX_URL", "PLEX_TOKEN", "TMDB_API_KEY", "PLEX_MEDIA_ROOT"]:
                if key in config:
                    f.write(f"{key}={config[key]}\n")

            f.write("\n# Optional Settings\n")
            for key in ["PLEX_INGEST_DIR", "PLEX_AUTO_INGEST",
                        "PLEX_CONFIDENCE_THRESHOLD", "PLEX_WATCHER_AUTO_START"]:
                if key in config:
                    f.write(f"{key}={config[key]}\n")

        print("✅ Configuration saved successfully!")
        return True

    except Exception as e:
        print(f"❌ Failed to save configuration: {e}")
        return False


def main():
    """Main configuration flow."""
    print_header()

    print("This wizard will help you configure the Plex MCP server.")
    print("You'll need:")
    print("  • Plex server URL and token")
    print("  • TMDb API key (free at themoviedb.org)")
    print("  • Path to your media library")
    print()

    if not prompt_yes_no("Ready to start?", default=True):
        print("Configuration cancelled.")
        return 1

    config = {}

    # Section 1: Plex Server
    print_section("1. Plex Server Configuration")

    print("Your Plex server URL (typically http://YOUR_IP:32400)")
    print("Examples:")
    print("  • http://localhost:32400 (if running locally)")
    print("  • http://192.168.1.100:32400 (local network)")

    while True:
        url = prompt_with_default("Plex URL", "http://localhost:32400")
        valid, msg = validate_url(url)
        if valid:
            config["PLEX_URL"] = url
            break
        else:
            print(f"❌ {msg}")

    print("\nYour Plex authentication token")
    print("Get it from: https://support.plex.tv/articles/204059436/")
    print("Quick method: Plex Web → Play media → Info → View XML → look for X-Plex-Token")

    config["PLEX_TOKEN"] = prompt_with_default("Plex Token")

    # Test Plex connection
    if prompt_yes_no("\nTest Plex connection now?", default=True):
        test_plex_connection(config["PLEX_URL"], config["PLEX_TOKEN"])

    # Section 2: TMDb API
    print_section("2. TMDb Configuration")

    print("TMDb provides movie/TV metadata for file identification.")
    print("Get a free API key at: https://www.themoviedb.org/settings/api")

    config["TMDB_API_KEY"] = prompt_with_default("TMDb API Key")

    # Test TMDb API
    if prompt_yes_no("\nTest TMDb API now?", default=True):
        test_tmdb_api(config["TMDB_API_KEY"])

    # Section 3: Media Paths
    print_section("3. Media Library Paths")

    print("Root directory where your Plex media is stored")
    print("Examples:")
    print("  • /Volumes/Media")
    print("  • /mnt/media")
    print("  • C:\\Media")

    while True:
        path = prompt_with_default("Media Root Path")
        valid, msg = validate_path(path, must_exist=True)
        if valid:
            config["PLEX_MEDIA_ROOT"] = path
            break
        else:
            print(f"❌ {msg}")
            if not prompt_yes_no("Continue anyway?", default=False):
                continue
            config["PLEX_MEDIA_ROOT"] = path
            break

    # Section 4: Optional Features
    print_section("4. Optional Features")

    if prompt_yes_no("Enable auto-ingest features? (watch folder for new media)", default=False):
        print("\nDirectory to watch for new media files")

        while True:
            path = prompt_with_default("Ingest Directory", default=None, required=False)
            if not path:
                break
            valid, msg = validate_path(path, must_exist=False)
            if valid or prompt_yes_no(f"{msg}. Continue anyway?", default=False):
                config["PLEX_INGEST_DIR"] = path
                break

        if "PLEX_INGEST_DIR" in config:
            config["PLEX_AUTO_INGEST"] = "true" if prompt_yes_no(
                "Automatically ingest high-confidence matches?", default=False
            ) else "false"

            threshold = prompt_with_default(
                "Confidence threshold for auto-ingest (0.0-1.0)",
                default="0.85"
            )
            config["PLEX_CONFIDENCE_THRESHOLD"] = threshold

            config["PLEX_WATCHER_AUTO_START"] = "true" if prompt_yes_no(
                "Start watcher automatically on server launch?", default=False
            ) else "false"

    # Summary
    print_section("Configuration Summary")

    print("Your configuration:")
    for key, value in config.items():
        # Mask sensitive values
        if "TOKEN" in key or "KEY" in key:
            display_value = value[:8] + "..." if len(value) > 8 else "***"
        else:
            display_value = value
        print(f"  {key}: {display_value}")

    # Save
    print()
    if not prompt_yes_no("Save this configuration?", default=True):
        print("Configuration cancelled.")
        return 1

    # Determine save location
    project_root = Path(__file__).parent
    env_file = project_root / ".env"

    if save_env_file(config, env_file):
        print()
        print("=" * 70)
        print("✅ Configuration Complete!")
        print("=" * 70)
        print()
        print("Next steps:")
        print(f"1. Test the server: uv run --env-file .env videodrome")
        print(f"2. Check the QUICKSTART.md for Claude Desktop setup")
        print(f"3. Use commands like /plex:status to verify connection")
        print()
        print(f"Configuration saved to: {env_file}")
        return 0
    else:
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Configuration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
