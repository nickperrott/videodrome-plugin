"""Tests for Transmission client wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from server.transmission import TransmissionClient, is_valid_torrent_reference


def test_is_valid_torrent_reference():
    """Torrent validation should accept magnet and .torrent URLs/paths."""
    assert is_valid_torrent_reference("magnet:?xt=urn:btih:abc123")
    assert is_valid_torrent_reference("https://example.com/file.torrent")
    assert is_valid_torrent_reference("https://example.com/file.TORRENT?token=abc")
    assert is_valid_torrent_reference("/tmp/file.torrent")
    assert not is_valid_torrent_reference("https://example.com/file.zip")
    assert not is_valid_torrent_reference("")


@patch("server.transmission.transmission_rpc.Client")
def test_connect_uses_url_protocol(mock_client_class):
    """Connection should honor the URL scheme for Transmission RPC."""
    mock_rpc_client = MagicMock()
    mock_rpc_client.get_session.return_value = MagicMock()
    mock_client_class.return_value = mock_rpc_client

    client = TransmissionClient("https://seedbox.example:8443/transmission/rpc")
    connected = client.connect()

    assert connected is True
    kwargs = mock_client_class.call_args.kwargs
    assert kwargs["protocol"] == "https"
    assert kwargs["host"] == "seedbox.example"
    assert kwargs["port"] == 8443
    assert kwargs["path"] == "/transmission/rpc"


def test_add_torrent_accepts_torrent_url_with_query():
    """Adding torrent should allow .torrent URLs with query parameters."""
    client = TransmissionClient("http://localhost:9091/transmission/rpc")
    client._client = MagicMock()

    rpc_result = MagicMock()
    rpc_result.id = 1
    rpc_result.name = "Example Torrent"
    rpc_result.hashString = "abc123"
    rpc_result.status = "downloading"
    rpc_result.download_dir = "/downloads"
    rpc_result.total_size = 1024
    rpc_result.percent_done = 0.5
    client._client.add_torrent.return_value = rpc_result

    result = client.add_torrent("https://example.com/file.TORRENT?token=abc")

    assert result["id"] == 1
    assert result["name"] == "Example Torrent"
    assert result["percent_done"] == 50.0


def test_add_torrent_rejects_non_torrent_url():
    """Adding torrent should reject URLs that are not magnet or .torrent."""
    client = TransmissionClient("http://localhost:9091/transmission/rpc")
    client._client = MagicMock()

    with pytest.raises(ValueError):
        client.add_torrent("https://example.com/file.zip")


def test_get_stats_uses_typed_stats_properties():
    """Stats should read typed fields exposed by transmission-rpc."""
    client = TransmissionClient("http://localhost:9091/transmission/rpc")
    client._client = MagicMock()

    current_stats = MagicMock()
    current_stats.downloaded_bytes = 111
    current_stats.uploaded_bytes = 222
    current_stats.files_added = 3

    stats = MagicMock()
    stats.active_torrent_count = 5
    stats.download_speed = 1000
    stats.upload_speed = 200
    stats.paused_torrent_count = 1
    stats.torrent_count = 7
    stats.current_stats = current_stats
    client._client.session_stats.return_value = stats

    result = client.get_stats()

    assert result["downloaded_bytes"] == 111
    assert result["uploaded_bytes"] == 222
    assert result["files_added"] == 3


def test_get_torrent_files_uses_get_files_api():
    """File extraction should use torrent.get_files() from transmission-rpc."""
    client = TransmissionClient("http://localhost:9091/transmission/rpc")

    file_info = MagicMock()
    file_info.name = "Movie/example.mkv"

    torrent = MagicMock()
    torrent.download_dir = "/downloads"
    torrent.get_files.return_value = [file_info]
    torrent.files.side_effect = AssertionError("Should not call deprecated files() API")

    files = client._get_torrent_files(torrent)

    torrent.get_files.assert_called_once()
    assert files == ["/downloads/Movie/example.mkv"]
