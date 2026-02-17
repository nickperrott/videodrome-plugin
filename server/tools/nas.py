"""NAS volume mount management tools for videodrome MCP."""

import os
import platform
import subprocess
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Environment variable keys
_NAS_IP_KEY = "VIDEODROME_NAS_IP"
_NAS_SHARE_KEY = "VIDEODROME_NAS_SHARE"
_NAS_MOUNT_KEY = "VIDEODROME_NAS_MOUNT_POINT"
_NAS_AUTO_MOUNT_KEY = "VIDEODROME_NAS_AUTO_MOUNT"


def _get_nas_config() -> Dict[str, str]:
    """Read NAS config from environment variables."""
    return {
        "nas_ip": os.environ.get(_NAS_IP_KEY, ""),
        "share_name": os.environ.get(_NAS_SHARE_KEY, "MEDIA"),
        "mount_point": os.environ.get(_NAS_MOUNT_KEY, "/Volumes/MEDIA"),
    }


def _is_truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_auto_mount_enabled() -> bool:
    """Whether automatic NAS mount attempts are enabled by configuration."""
    return _is_truthy(os.environ.get(_NAS_AUTO_MOUNT_KEY, "false"))


async def check_media_volume() -> Dict[str, Any]:
    """Check if the NAS MEDIA volume is currently mounted and accessible.

    Reads NAS configuration from environment variables:
        VIDEODROME_NAS_IP         - NAS server IP (e.g. 10.9.8.15)
        VIDEODROME_NAS_SHARE      - SMB share name (default: MEDIA)
        VIDEODROME_NAS_MOUNT_POINT - Local mount point (default: /Volumes/MEDIA)

    Returns:
        Dictionary with mount status, path, accessibility, and NAS details.
    """
    cfg = _get_nas_config()
    mount_point = Path(cfg["mount_point"])

    mounted = mount_point.exists()
    accessible = False
    if mounted:
        try:
            # Confirm it's an actual mount (has readable content) by listing root
            next(mount_point.iterdir(), None)
            accessible = True
        except (PermissionError, OSError):
            accessible = False

    result = {
        "mounted": mounted,
        "accessible": accessible,
        "path": str(mount_point),
        "nas_ip": cfg["nas_ip"],
        "share_name": cfg["share_name"],
        "auto_mount_enabled": is_auto_mount_enabled(),
    }

    if not mounted:
        result["hint"] = (
            f"Run mount_media_volume() to mount //{cfg['nas_ip']}/{cfg['share_name']} "
            f"at {cfg['mount_point']}"
        )

    return result


async def ensure_media_volume_for_path(path: str | Path) -> Dict[str, Any]:
    """Auto-mount the configured NAS volume when path access requires it."""
    cfg = _get_nas_config()
    mount_point = Path(cfg["mount_point"])
    target_path = Path(path)

    if not is_auto_mount_enabled():
        return {"attempted": False, "reason": "auto_mount_disabled"}

    try:
        target_path.resolve(strict=False).relative_to(mount_point.resolve(strict=False))
    except ValueError:
        return {"attempted": False, "reason": "path_outside_mount_point"}

    if mount_point.exists():
        try:
            next(mount_point.iterdir(), None)
            return {"attempted": False, "reason": "already_mounted"}
        except (PermissionError, OSError):
            # Stale mount or inaccessible path; continue to mount attempt.
            pass

    mount_result = await mount_media_volume(force_remount=False)
    return {"attempted": True, **mount_result}


async def mount_media_volume(force_remount: bool = False) -> Dict[str, Any]:
    """Mount the NAS MEDIA SMB share.

    Uses platform-appropriate mounting:
        macOS:  open smb://<NAS_IP>/<SHARE>  (uses Finder / current user creds)
        Linux:  mount -t cifs //<NAS_IP>/<SHARE> <MOUNT_POINT> -o username=$USER

    Args:
        force_remount: If True, unmount first even if already mounted (macOS only).

    Returns:
        Dictionary with success status and mount path.
    """
    cfg = _get_nas_config()

    if not cfg["nas_ip"]:
        return {
            "success": False,
            "error": (
                f"NAS IP not configured. "
                f"Set {_NAS_IP_KEY} in your .env file (e.g. VIDEODROME_NAS_IP=10.9.8.15)"
            ),
        }

    mount_point = Path(cfg["mount_point"])
    nas_ip = cfg["nas_ip"]
    share_name = cfg["share_name"]
    smb_url = f"smb://{nas_ip}/{share_name}"

    # Check if already mounted
    if mount_point.exists() and not force_remount:
        try:
            next(mount_point.iterdir(), None)
            return {
                "success": True,
                "mounted": True,
                "path": str(mount_point),
                "message": f"Volume already mounted at {mount_point}",
            }
        except (PermissionError, OSError):
            pass  # Stale mount — fall through to remount

    system = platform.system()

    try:
        if system == "Darwin":
            # macOS: use 'open' to trigger Finder/SMB mount with user credentials
            result = subprocess.run(
                ["open", smb_url],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"mount failed: {result.stderr.strip() or 'unknown error'}",
                    "command": f"open {smb_url}",
                }
            # Give the system a moment to complete the mount
            import asyncio
            await asyncio.sleep(2)
        elif system == "Linux":
            # Linux: use mount with cifs
            mount_point.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [
                    "mount", "-t", "cifs",
                    f"//{nas_ip}/{share_name}",
                    str(mount_point),
                    "-o", f"username={os.environ.get('USER', 'guest')}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"mount failed: {result.stderr.strip() or 'unknown error'}",
                }
        else:
            return {
                "success": False,
                "error": f"Unsupported platform: {system}. Mount manually with: net use M: \\\\{nas_ip}\\{share_name}",
            }

        # Verify the mount succeeded
        if mount_point.exists():
            return {
                "success": True,
                "mounted": True,
                "path": str(mount_point),
                "message": f"Mounted {smb_url} at {mount_point}",
            }
        else:
            return {
                "success": False,
                "error": f"Mount command succeeded but {mount_point} is not accessible. "
                         f"Check NAS credentials and share name.",
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Mount timed out connecting to {nas_ip}. Check network connectivity.",
        }
    except Exception as e:
        logger.error("Unexpected error mounting NAS volume: %s", e)
        return {"success": False, "error": str(e)}
