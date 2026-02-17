"""
Safety classification for Plex MCP tools.

Provides three-tier safety model:
- READ: Safe operations that can be auto-approved
- WRITE: Operations requiring confirmation
- BLOCKED: Dangerous operations that should be denied
"""

from enum import Enum
from typing import Any


class SafetyTier(Enum):
    """Safety classification for tool operations."""
    READ = "read"
    WRITE = "write"
    BLOCKED = "blocked"


# Tool classification by name prefix
TOOL_SAFETY_MAP: dict[str, SafetyTier] = {
    # READ-ONLY TOOLS (auto-approved)
    # Library operations
    "plex_list_libraries": SafetyTier.READ,
    "plex_get_library_stats": SafetyTier.READ,
    "plex_search_library": SafetyTier.READ,
    "plex_list_recent": SafetyTier.READ,
    "plex_get_server_info": SafetyTier.READ,

    # Media identification
    "plex_parse_filename": SafetyTier.READ,
    "plex_search_tmdb": SafetyTier.READ,
    "plex_get_tmdb_metadata": SafetyTier.READ,
    "plex_preview_rename": SafetyTier.READ,
    "plex_batch_identify": SafetyTier.READ,

    # Queue and history
    "plex_get_ingest_queue": SafetyTier.READ,
    "plex_get_queue_item": SafetyTier.READ,
    "plex_query_history": SafetyTier.READ,
    "plex_get_watcher_status": SafetyTier.READ,

    # Duplicate detection
    "plex_check_duplicates": SafetyTier.READ,

    # File operations (read-only)
    "plex_scan_directory": SafetyTier.READ,
    "plex_list_video_files": SafetyTier.READ,

    # WRITE TOOLS (require confirmation)
    # Library modifications
    "plex_scan_library": SafetyTier.WRITE,

    # File operations
    "plex_execute_naming_plan": SafetyTier.WRITE,
    "plex_execute_ingest": SafetyTier.WRITE,
    "plex_copy_file": SafetyTier.WRITE,
    "plex_rename_file": SafetyTier.WRITE,
    "plex_move_file": SafetyTier.WRITE,
    "plex_organize_file": SafetyTier.WRITE,

    # Queue operations
    "plex_approve_queue_item": SafetyTier.WRITE,
    "plex_reject_queue_item": SafetyTier.WRITE,

    # Watcher operations
    "plex_start_watcher": SafetyTier.WRITE,
    "plex_stop_watcher": SafetyTier.WRITE,
    "plex_restart_watcher": SafetyTier.WRITE,
    "plex_configure_watcher": SafetyTier.WRITE,

    # Plex library — season/inventory tools
    "get_library_inventory": SafetyTier.READ,
    "get_show_details": SafetyTier.READ,

    # Torrent search tools (all read-only — no side effects)
    "search_torrents": SafetyTier.READ,
    "get_torrent_magnet": SafetyTier.READ,
    "search_season": SafetyTier.READ,

    # NAS volume management
    "check_media_volume": SafetyTier.READ,
    "mount_media_volume": SafetyTier.WRITE,  # triggers OS-level mount

    # Discovery / agentic workflows
    "find_new_seasons": SafetyTier.READ,
    "discover_top_rated_content": SafetyTier.READ,

    # BLOCKED TOOLS (always denied)
    "plex_delete_file": SafetyTier.BLOCKED,
    "plex_delete_directory": SafetyTier.BLOCKED,
    "plex_delete_library": SafetyTier.BLOCKED,
    "plex_remove_file": SafetyTier.BLOCKED,
}


def get_tool_safety(tool_name: str) -> SafetyTier:
    """
    Get the safety tier for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        SafetyTier classification
    """
    # Default to WRITE for unknown tools (safe default)
    return TOOL_SAFETY_MAP.get(tool_name, SafetyTier.WRITE)


def is_safe_operation(tool_name: str) -> bool:
    """
    Check if a tool is safe to execute without confirmation.

    Args:
        tool_name: Name of the tool

    Returns:
        True if tool is READ tier (safe), False otherwise
    """
    return get_tool_safety(tool_name) == SafetyTier.READ


def is_blocked_operation(tool_name: str) -> bool:
    """
    Check if a tool is blocked and should never execute.

    Args:
        tool_name: Name of the tool

    Returns:
        True if tool is BLOCKED tier, False otherwise
    """
    return get_tool_safety(tool_name) == SafetyTier.BLOCKED


def validate_operation(tool_name: str) -> tuple[bool, str | None]:
    """
    Validate if a tool operation should be allowed.

    Args:
        tool_name: Name of the tool

    Returns:
        Tuple of (allowed, reason):
        - allowed: True if operation should proceed
        - reason: Explanation if operation is blocked
    """
    tier = get_tool_safety(tool_name)

    if tier == SafetyTier.BLOCKED:
        return False, (
            f"Operation '{tool_name}' is blocked for safety reasons. "
            "Deletion operations are not permitted through this plugin."
        )

    return True, None


def get_safety_metadata(tool_name: str) -> dict[str, Any]:
    """
    Get safety metadata for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Dictionary with safety information
    """
    tier = get_tool_safety(tool_name)
    allowed, reason = validate_operation(tool_name)

    return {
        "tier": tier.value,
        "allowed": allowed,
        "blocked_reason": reason,
        "requires_confirmation": tier == SafetyTier.WRITE,
        "auto_approved": tier == SafetyTier.READ,
    }
