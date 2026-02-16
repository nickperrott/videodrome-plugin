"""
Three-tier safety hook for Plex MCP server.

Implements safety classification for all tool operations:
- READ: Safe, auto-approved operations (queries, previews, analysis)
- WRITE: Operations requiring user confirmation (ingest, scan, rename)
- BLOCKED: Dangerous operations that are always denied (delete)

This hook is called before every tool invocation to determine if user
confirmation is required.
"""

from enum import Enum
from typing import Any


class SafetyTier(Enum):
    """Safety classification for tool operations."""
    READ = "read"      # Auto-approved, no confirmation needed
    WRITE = "write"    # Requires user confirmation
    BLOCKED = "blocked"  # Always denied


# Tool classification by name
TOOL_SAFETY_MAP: dict[str, SafetyTier] = {
    # READ-ONLY TOOLS (auto-approved)
    # Library operations
    "list_libraries": SafetyTier.READ,
    "get_library_stats": SafetyTier.READ,
    "search_library": SafetyTier.READ,
    "list_recent": SafetyTier.READ,
    "get_server_info": SafetyTier.READ,

    # Media identification
    "parse_filename": SafetyTier.READ,
    "search_tmdb": SafetyTier.READ,
    "get_tmdb_metadata": SafetyTier.READ,
    "preview_rename": SafetyTier.READ,
    "batch_identify": SafetyTier.READ,

    # Queue and history
    "get_ingest_queue": SafetyTier.READ,
    "get_queue_item": SafetyTier.READ,
    "query_history": SafetyTier.READ,
    "get_watcher_status": SafetyTier.READ,

    # Duplicate detection
    "check_duplicates": SafetyTier.READ,

    # WRITE TOOLS (require confirmation)
    # Library operations
    "scan_library": SafetyTier.WRITE,
    "refresh_metadata": SafetyTier.WRITE,

    # File operations
    "execute_naming_plan": SafetyTier.WRITE,
    "execute_ingest": SafetyTier.WRITE,
    "copy_file": SafetyTier.WRITE,
    "rename_file": SafetyTier.WRITE,
    "move_file": SafetyTier.WRITE,

    # Queue management
    "approve_queue_item": SafetyTier.WRITE,
    "reject_queue_item": SafetyTier.WRITE,

    # Watcher control
    "start_watcher": SafetyTier.WRITE,
    "stop_watcher": SafetyTier.WRITE,
    "restart_watcher": SafetyTier.WRITE,

    # BLOCKED TOOLS (always denied)
    "delete_file": SafetyTier.BLOCKED,
    "delete_directory": SafetyTier.BLOCKED,
    "delete_library": SafetyTier.BLOCKED,
    "remove_file": SafetyTier.BLOCKED,
}


def classify_tool_safety(tool_name: str, tool_args: dict[str, Any]) -> SafetyTier:
    """
    Classify a tool operation into a safety tier.

    Args:
        tool_name: Name of the tool being invoked
        tool_args: Arguments passed to the tool

    Returns:
        SafetyTier indicating required safety level

    Raises:
        ValueError: If tool_name is not recognized
    """
    if tool_name not in TOOL_SAFETY_MAP:
        # Unknown tools default to WRITE (safe default: require confirmation)
        return SafetyTier.WRITE

    return TOOL_SAFETY_MAP[tool_name]


def should_allow_operation(tier: SafetyTier) -> tuple[bool, str | None]:
    """
    Determine if an operation should be allowed based on its safety tier.

    Args:
        tier: SafetyTier classification

    Returns:
        Tuple of (allowed, reason):
        - allowed: True if operation should proceed
        - reason: Explanation if operation is blocked
    """
    if tier == SafetyTier.BLOCKED:
        return False, "This operation is blocked for safety reasons. Deletion operations are not permitted through this plugin."

    # READ and WRITE operations are allowed
    # (WRITE operations will trigger confirmation prompts at the MCP server level)
    return True, None


def get_confirmation_message(tool_name: str, tool_args: dict[str, Any]) -> str:
    """
    Generate a user-friendly confirmation message for WRITE operations.

    Args:
        tool_name: Name of the tool being invoked
        tool_args: Arguments passed to the tool

    Returns:
        Confirmation message string
    """
    messages = {
        "scan_library": "Trigger a library scan? This will refresh Plex metadata and may be resource-intensive.",
        "execute_naming_plan": "Execute renaming plan? Files will be moved and renamed on disk.",
        "execute_ingest": "Execute full ingest pipeline? Files will be copied/moved to Plex libraries.",
        "copy_file": "Copy file to Plex library? This will modify the filesystem.",
        "rename_file": "Rename file? This will modify the filesystem.",
        "move_file": "Move file? This will modify the filesystem.",
        "approve_queue_item": "Approve and ingest this file? It will be processed and added to Plex.",
        "reject_queue_item": "Reject this file? It will be removed from the ingest queue.",
        "start_watcher": "Start file watcher? New files will be automatically processed based on confidence threshold.",
        "stop_watcher": "Stop file watcher? Automatic file processing will be disabled.",
        "restart_watcher": "Restart file watcher? This will stop and restart automatic file processing.",
    }

    base_message = messages.get(
        tool_name,
        f"Execute {tool_name}? This operation will modify data or trigger actions."
    )

    # Add context from arguments if available
    if tool_name == "scan_library" and "library_name" in tool_args:
        library = tool_args["library_name"] or "all libraries"
        return f"Trigger scan for {library}? This will refresh Plex metadata."

    if tool_name in ("execute_ingest", "approve_queue_item") and "source_path" in tool_args:
        return f"{base_message}\nSource: {tool_args['source_path']}"

    return base_message


def safety_hook(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    """
    Main safety hook called before tool execution.

    This function is called by the MCP server before invoking any tool.
    It classifies the operation and determines if it should be allowed.

    Args:
        tool_name: Name of the tool being invoked
        tool_args: Arguments passed to the tool

    Returns:
        Dictionary with safety check results:
        {
            "tier": str,           # Safety tier: "read", "write", or "blocked"
            "allowed": bool,       # Whether operation should proceed
            "reason": str | None,  # Explanation if blocked
            "requires_confirmation": bool,  # Whether user confirmation is needed
            "confirmation_message": str | None  # Message for confirmation prompt
        }
    """
    tier = classify_tool_safety(tool_name, tool_args)
    allowed, reason = should_allow_operation(tier)

    result = {
        "tier": tier.value,
        "allowed": allowed,
        "reason": reason,
        "requires_confirmation": tier == SafetyTier.WRITE,
        "confirmation_message": None,
    }

    if tier == SafetyTier.WRITE:
        result["confirmation_message"] = get_confirmation_message(tool_name, tool_args)

    return result


# Example usage and testing
if __name__ == "__main__":
    # Test READ operation
    result = safety_hook("list_libraries", {})
    assert result["tier"] == "read"
    assert result["allowed"] is True
    assert result["requires_confirmation"] is False
    print("✓ READ operation test passed")

    # Test WRITE operation
    result = safety_hook("scan_library", {"library_name": "Movies"})
    assert result["tier"] == "write"
    assert result["allowed"] is True
    assert result["requires_confirmation"] is True
    assert "Movies" in result["confirmation_message"]
    print("✓ WRITE operation test passed")

    # Test BLOCKED operation
    result = safety_hook("delete_file", {"path": "/some/file.mkv"})
    assert result["tier"] == "blocked"
    assert result["allowed"] is False
    assert "blocked" in result["reason"].lower()
    assert result["requires_confirmation"] is False
    print("✓ BLOCKED operation test passed")

    # Test unknown tool (defaults to WRITE)
    result = safety_hook("unknown_tool", {})
    assert result["tier"] == "write"
    assert result["allowed"] is True
    assert result["requires_confirmation"] is True
    print("✓ Unknown tool defaults to WRITE test passed")

    print("\n✓ All safety hook tests passed!")
