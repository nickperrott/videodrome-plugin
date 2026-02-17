"""Tests for NAS volume mount tools."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from server.tools.nas import (
    check_media_volume,
    mount_media_volume,
    ensure_media_volume_for_path,
)


# =============================================================================
# check_media_volume tests
# =============================================================================


@pytest.mark.asyncio
async def test_check_volume_mounted_and_accessible(tmp_path):
    """check_media_volume should report mounted=True when path exists and is readable."""
    # Create a dummy file so iterdir() finds something
    (tmp_path / "dummy.txt").write_text("x")

    env = {
        "VIDEODROME_NAS_IP": "10.9.8.15",
        "VIDEODROME_NAS_SHARE": "MEDIA",
        "VIDEODROME_NAS_MOUNT_POINT": str(tmp_path),
    }
    with patch.dict("os.environ", env, clear=False):
        result = await check_media_volume()

    assert result["mounted"] is True
    assert result["accessible"] is True
    assert "hint" not in result


@pytest.mark.asyncio
async def test_check_volume_not_mounted(tmp_path):
    """check_media_volume should report mounted=False for non-existent path."""
    missing = tmp_path / "nonexistent"

    env = {
        "VIDEODROME_NAS_IP": "10.9.8.15",
        "VIDEODROME_NAS_SHARE": "MEDIA",
        "VIDEODROME_NAS_MOUNT_POINT": str(missing),
    }
    with patch.dict("os.environ", env, clear=False):
        result = await check_media_volume()

    assert result["mounted"] is False
    assert result["accessible"] is False
    assert "hint" in result


@pytest.mark.asyncio
async def test_check_volume_includes_nas_details():
    """check_media_volume should include NAS IP and share name in response."""
    env = {
        "VIDEODROME_NAS_IP": "192.168.1.50",
        "VIDEODROME_NAS_SHARE": "DATA",
        "VIDEODROME_NAS_MOUNT_POINT": "/nonexistent/path",
    }
    with patch.dict("os.environ", env, clear=False):
        result = await check_media_volume()

    assert result["nas_ip"] == "192.168.1.50"
    assert result["share_name"] == "DATA"


@pytest.mark.asyncio
async def test_ensure_media_volume_for_path_skips_when_auto_mount_disabled(tmp_path):
    """ensure_media_volume_for_path should no-op when auto-mount is disabled."""
    mount_point = tmp_path / "MEDIA"
    target = mount_point / "Movies" / "file.mkv"

    env = {
        "VIDEODROME_NAS_MOUNT_POINT": str(mount_point),
        "VIDEODROME_NAS_AUTO_MOUNT": "false",
    }
    with patch.dict("os.environ", env, clear=False):
        result = await ensure_media_volume_for_path(target)

    assert result["attempted"] is False
    assert result["reason"] == "auto_mount_disabled"


@pytest.mark.asyncio
async def test_ensure_media_volume_for_path_attempts_mount_when_enabled(tmp_path):
    """ensure_media_volume_for_path should trigger mount for paths on configured NAS volume."""
    mount_point = tmp_path / "MEDIA"
    target = mount_point / "TV Shows" / "show.mkv"

    env = {
        "VIDEODROME_NAS_IP": "10.9.8.15",
        "VIDEODROME_NAS_SHARE": "MEDIA",
        "VIDEODROME_NAS_MOUNT_POINT": str(mount_point),
        "VIDEODROME_NAS_AUTO_MOUNT": "true",
    }
    with patch.dict("os.environ", env, clear=False), \
         patch("server.tools.nas.mount_media_volume", new_callable=AsyncMock) as mock_mount:
        mock_mount.return_value = {"success": True, "mounted": True, "path": str(mount_point)}
        result = await ensure_media_volume_for_path(target)

    assert result["attempted"] is True
    assert result["success"] is True
    mock_mount.assert_awaited_once()


# =============================================================================
# mount_media_volume tests
# =============================================================================


@pytest.mark.asyncio
async def test_mount_volume_missing_nas_ip():
    """mount_media_volume should return error when NAS IP is not configured."""
    env = {"VIDEODROME_NAS_IP": "", "VIDEODROME_NAS_SHARE": "MEDIA", "VIDEODROME_NAS_MOUNT_POINT": "/Volumes/MEDIA"}
    with patch.dict("os.environ", env, clear=False):
        result = await mount_media_volume()

    assert result["success"] is False
    assert "VIDEODROME_NAS_IP" in result["error"]


@pytest.mark.asyncio
async def test_mount_volume_already_mounted(tmp_path):
    """mount_media_volume should report success immediately if already mounted."""
    (tmp_path / "file.txt").write_text("x")

    env = {
        "VIDEODROME_NAS_IP": "10.9.8.15",
        "VIDEODROME_NAS_SHARE": "MEDIA",
        "VIDEODROME_NAS_MOUNT_POINT": str(tmp_path),
    }
    with patch.dict("os.environ", env, clear=False):
        result = await mount_media_volume()

    assert result["success"] is True
    assert result["mounted"] is True
    assert "already mounted" in result["message"]


@pytest.mark.asyncio
async def test_mount_volume_macos_calls_open():
    """mount_media_volume on macOS should call 'open smb://…' (force_remount bypasses already-mounted check)."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0

    env = {
        "VIDEODROME_NAS_IP": "10.9.8.15",
        "VIDEODROME_NAS_SHARE": "MEDIA",
        "VIDEODROME_NAS_MOUNT_POINT": "/Volumes/MEDIA",
    }

    with patch.dict("os.environ", env, clear=False), \
         patch("platform.system", return_value="Darwin"), \
         patch("subprocess.run", return_value=mock_proc) as mock_run, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        # force_remount=True skips the "already mounted" early return
        result = await mount_media_volume(force_remount=True)

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]  # positional args list
    assert call_args[0] == "open"
    assert "smb://10.9.8.15/MEDIA" in call_args[1]


@pytest.mark.asyncio
async def test_mount_volume_subprocess_failure():
    """mount_media_volume should return success=False on non-zero returncode."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stderr = "Host not found"

    env = {
        "VIDEODROME_NAS_IP": "10.9.8.15",
        "VIDEODROME_NAS_SHARE": "MEDIA",
        "VIDEODROME_NAS_MOUNT_POINT": "/Volumes/NONEXISTENT",
    }

    with patch.dict("os.environ", env, clear=False), \
         patch("platform.system", return_value="Darwin"), \
         patch("subprocess.run", return_value=mock_proc), \
         patch("pathlib.Path.exists", return_value=False):
        result = await mount_media_volume()

    assert result["success"] is False
    assert "error" in result
