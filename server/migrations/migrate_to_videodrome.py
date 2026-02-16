#!/usr/bin/env python3
"""Migrate plex-mcp configuration and databases to videodrome."""

import shutil
from pathlib import Path


def migrate_config():
    """Migrate configuration directory and update environment variables."""
    old_config = Path.home() / ".config" / "plex-mcp"
    new_config = Path.home() / ".config" / "videodrome"

    if old_config.exists() and not new_config.exists():
        print(f"Migrating config: {old_config} → {new_config}")
        new_config.mkdir(parents=True, exist_ok=True)

        # Migrate .env file with variable name updates
        old_env = old_config / ".env"
        new_env = new_config / ".env"

        if old_env.exists():
            with open(old_env) as f:
                content = f.read()

            # Update variable names (preserve values)
            replacements = {
                "PLEX_URL=": "VIDEODROME_PLEX_URL=",
                "PLEX_TOKEN=": "VIDEODROME_PLEX_TOKEN=",
                "TMDB_API_KEY=": "VIDEODROME_TMDB_API_KEY=",
                "PLEX_MEDIA_ROOT=": "VIDEODROME_MEDIA_ROOT=",
                "PLEX_INGEST_DIR=": "VIDEODROME_INGEST_DIR=",
                "PLEX_AUTO_INGEST=": "VIDEODROME_AUTO_INGEST=",
                "PLEX_CONFIDENCE_THRESHOLD=": "VIDEODROME_CONFIDENCE_THRESHOLD=",
                "PLEX_WATCHER_AUTO_START=": "VIDEODROME_WATCHER_AUTO_START=",
            }

            for old, new in replacements.items():
                content = content.replace(old, new)

            with open(new_env, 'w') as f:
                f.write(content)

            print(f"  ✓ Migrated and updated {new_env}")
        else:
            print(f"  ⚠ No .env file found in {old_config}")
    elif new_config.exists():
        print(f"  ℹ Config already migrated to {new_config}")
    else:
        print(f"  ℹ No old config found at {old_config}")


def migrate_cache():
    """Migrate cache directory (databases)."""
    old_cache = Path.home() / ".cache" / "plex-mcp"
    new_cache = Path.home() / ".cache" / "videodrome"

    if old_cache.exists() and not new_cache.exists():
        print(f"Migrating cache: {old_cache} → {new_cache}")
        shutil.copytree(old_cache, new_cache)
        print(f"  ✓ Migrated databases to {new_cache}")
    elif new_cache.exists():
        print(f"  ℹ Cache already migrated to {new_cache}")
    else:
        print(f"  ℹ No old cache found at {old_cache}")


def main():
    print("=" * 60)
    print("Videodrome Migration Tool")
    print("=" * 60)
    print()

    migrate_config()
    print()
    migrate_cache()
    print()

    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Verify ~/.config/videodrome/.env has correct settings")
    print("2. Update Claude Desktop config to use 'videodrome' server")
    print("3. Reinstall Claude Code plugin: videodrome-plugin/")
    print()


if __name__ == "__main__":
    main()
