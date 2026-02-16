#!/usr/bin/env python3
"""Manual test script for Plex MCP Server.

This script tests the server with mock environment variables.
It won't actually connect to a Plex server, but will verify the code structure.
"""

import asyncio
import os
import sys

# Set mock environment variables
os.environ["PLEX_URL"] = "http://localhost:32400"
os.environ["PLEX_TOKEN"] = "fake-token-for-testing"
os.environ["TMDB_API_KEY"] = "fake-tmdb-key"
os.environ["PLEX_MEDIA_ROOT"] = "/tmp/media"
os.environ["PLEX_INGEST_DIR"] = "/tmp/ingest"

async def test_server_structure():
    """Test that the server structure is correct without connecting."""
    print("=" * 60)
    print("Plex MCP Server - Structure Test")
    print("=" * 60)

    # Import should work
    print("\n1. Testing imports...")
    try:
        from server.main import mcp
        print("   ✓ Server imports successfully")
    except Exception as e:
        print(f"   ✗ Import failed: {e}")
        return False

    # Check server name
    print(f"\n2. Server name: {mcp.name}")

    # List tools
    print("\n3. Listing registered tools...")
    try:
        tools = await mcp.list_tools()
        print(f"   ✓ Found {len(tools)} registered tools")

        categories = {}
        for tool in tools:
            # Categorize by first word
            category = tool.name.split("_")[0] if "_" in tool.name else tool.name
            if category not in categories:
                categories[category] = []
            categories[category].append(tool.name)

        print("\n   Tools by category:")
        for category, tool_names in sorted(categories.items()):
            print(f"   - {category}: {len(tool_names)} tools")
            for name in sorted(tool_names)[:3]:
                print(f"      • {name}")
            if len(tool_names) > 3:
                print(f"      ... and {len(tool_names) - 3} more")

    except Exception as e:
        print(f"   ✗ Failed to list tools: {e}")
        return False

    print("\n" + "=" * 60)
    print("✓ All structure tests passed!")
    print("=" * 60)
    print("\nNote: To actually run the server, you need:")
    print("1. A running Plex Media Server")
    print("2. Valid PLEX_URL and PLEX_TOKEN")
    print("3. Valid TMDB_API_KEY")
    print("4. Run with: uv run videodrome")

    return True


if __name__ == "__main__":
    result = asyncio.run(test_server_structure())
    sys.exit(0 if result else 1)
