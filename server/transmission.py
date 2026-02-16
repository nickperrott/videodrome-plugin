"""Transmission BitTorrent client wrapper for automated downloads."""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from urllib.parse import urlparse

import transmission_rpc
from transmission_rpc.error import TransmissionError


logger = logging.getLogger(__name__)


def is_valid_torrent_reference(torrent: str) -> bool:
    """Validate accepted torrent references (magnet URI or .torrent path/URL)."""
    if not torrent:
        return False

    if torrent.startswith("magnet:"):
        return True

    parsed = urlparse(torrent)
    torrent_path = parsed.path or torrent
    return Path(torrent_path).suffix.lower() == ".torrent"


class TransmissionClient:
    """Wrapper for Transmission RPC client."""

    def __init__(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize Transmission client.

        Args:
            url: Transmission RPC URL (e.g., http://localhost:9091/transmission/rpc)
            username: Optional username for authentication
            password: Optional password for authentication
        """
        self.url = url
        self.username = username
        self.password = password
        self._client: Optional[transmission_rpc.Client] = None
        self._is_connected = False

    def connect(self) -> bool:
        """
        Connect to Transmission daemon.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Parse URL to extract host, port, path
            parsed = urlparse(self.url)
            protocol = parsed.scheme.lower() if parsed.scheme else "http"
            if protocol not in {"http", "https"}:
                protocol = "http"
            host = parsed.hostname or "localhost"
            port = parsed.port or 9091
            path = parsed.path or "/transmission/rpc"
            if not path.startswith("/"):
                path = f"/{path}"

            logger.info(f"Connecting to Transmission at {protocol}://{host}:{port}{path}")

            self._client = transmission_rpc.Client(
                protocol=protocol,
                host=host,
                port=port,
                path=path,
                username=self.username,
                password=self.password
            )

            # Test connection
            self._client.get_session()
            self._is_connected = True
            logger.info("Successfully connected to Transmission")
            return True

        except TransmissionError as e:
            logger.error(f"Failed to connect to Transmission: {e}")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Transmission: {e}")
            self._is_connected = False
            return False

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._is_connected

    def add_torrent(
        self,
        torrent: str,
        download_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a torrent to Transmission.

        Args:
            torrent: Magnet URI or .torrent file URL
            download_dir: Optional download directory (must be under PLEX_INGEST_DIR)

        Returns:
            Dict with torrent information

        Raises:
            ValueError: If torrent format is invalid
            TransmissionError: If add operation fails
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        # Validate torrent format
        if not is_valid_torrent_reference(torrent):
            raise ValueError(
                "Invalid torrent format. Must be a magnet URI (magnet:) "
                "or .torrent URL/path"
            )

        try:
            logger.info(f"Adding torrent: {torrent[:80]}...")

            # Add torrent with optional download directory
            kwargs = {"download_dir": download_dir} if download_dir else {}
            result = self._client.add_torrent(torrent, **kwargs)

            return {
                "id": result.id,
                "name": result.name,
                "hash": result.hashString,
                "status": result.status,
                "download_dir": result.download_dir,
                "total_size": result.total_size,
                "percent_done": result.percent_done * 100
            }

        except TransmissionError as e:
            logger.error(f"Failed to add torrent: {e}")
            raise

    def list_torrents(
        self,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all torrents with optional status filter.

        Args:
            status_filter: Filter by status (downloading/seeding/stopped/all)

        Returns:
            List of torrent information dictionaries
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        try:
            torrents = self._client.get_torrents()

            results = []
            for torrent in torrents:
                # Apply status filter if specified
                if status_filter:
                    torrent_status = torrent.status.lower()
                    if status_filter.lower() == "downloading" and torrent_status not in ["downloading", "download pending"]:
                        continue
                    elif status_filter.lower() == "seeding" and torrent_status != "seeding":
                        continue
                    elif status_filter.lower() == "stopped" and torrent_status != "stopped":
                        continue

                results.append({
                    "id": torrent.id,
                    "name": torrent.name,
                    "hash": torrent.hashString,
                    "status": torrent.status,
                    "download_dir": torrent.download_dir,
                    "total_size": torrent.total_size,
                    "downloaded": torrent.downloaded_ever,
                    "uploaded": torrent.uploaded_ever,
                    "percent_done": round(torrent.percent_done * 100, 2),
                    "eta": torrent.eta.seconds if torrent.eta else None,
                    "rate_download": torrent.rate_download,
                    "rate_upload": torrent.rate_upload
                })

            return results

        except TransmissionError as e:
            logger.error(f"Failed to list torrents: {e}")
            raise

    def get_torrent_status(self, torrent_id: int) -> Dict[str, Any]:
        """
        Get detailed status of a specific torrent.

        Args:
            torrent_id: Torrent ID

        Returns:
            Dict with detailed torrent information
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        try:
            torrent = self._client.get_torrent(torrent_id)

            return {
                "id": torrent.id,
                "name": torrent.name,
                "hash": torrent.hashString,
                "status": torrent.status,
                "download_dir": torrent.download_dir,
                "total_size": torrent.total_size,
                "downloaded": torrent.downloaded_ever,
                "uploaded": torrent.uploaded_ever,
                "percent_done": round(torrent.percent_done * 100, 2),
                "eta": torrent.eta.seconds if torrent.eta else None,
                "rate_download": torrent.rate_download,
                "rate_upload": torrent.rate_upload,
                "peers_connected": torrent.peers_connected,
                "seeds_connected": torrent.peers_sending_to_us,
                "error": torrent.error_string if torrent.error else None,
                "date_added": torrent.date_added.isoformat() if torrent.date_added else None,
                "date_done": torrent.date_done.isoformat() if torrent.date_done else None
            }

        except TransmissionError as e:
            logger.error(f"Failed to get torrent status: {e}")
            raise

    def pause_torrent(self, torrent_id: int) -> Dict[str, Any]:
        """
        Pause a torrent download.

        Args:
            torrent_id: Torrent ID

        Returns:
            Status message
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        try:
            self._client.stop_torrent(torrent_id)
            logger.info(f"Paused torrent ID: {torrent_id}")
            return {"status": "success", "message": f"Torrent {torrent_id} paused"}

        except TransmissionError as e:
            logger.error(f"Failed to pause torrent: {e}")
            raise

    def resume_torrent(self, torrent_id: int) -> Dict[str, Any]:
        """
        Resume a paused torrent.

        Args:
            torrent_id: Torrent ID

        Returns:
            Status message
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        try:
            self._client.start_torrent(torrent_id)
            logger.info(f"Resumed torrent ID: {torrent_id}")
            return {"status": "success", "message": f"Torrent {torrent_id} resumed"}

        except TransmissionError as e:
            logger.error(f"Failed to resume torrent: {e}")
            raise

    def remove_torrent(
        self,
        torrent_id: int,
        delete_data: bool = False
    ) -> Dict[str, Any]:
        """
        Remove a torrent from Transmission.

        Args:
            torrent_id: Torrent ID
            delete_data: Also delete downloaded data

        Returns:
            Status message
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        try:
            self._client.remove_torrent(torrent_id, delete_data=delete_data)
            action = "removed with data" if delete_data else "removed"
            logger.info(f"Torrent ID {torrent_id} {action}")
            return {
                "status": "success",
                "message": f"Torrent {torrent_id} {action}"
            }

        except TransmissionError as e:
            logger.error(f"Failed to remove torrent: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Transmission daemon statistics.

        Returns:
            Dict with daemon statistics
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        try:
            stats = self._client.session_stats()

            return {
                "active_torrent_count": stats.active_torrent_count,
                "download_speed": stats.download_speed,
                "upload_speed": stats.upload_speed,
                "paused_torrent_count": stats.paused_torrent_count,
                "torrent_count": stats.torrent_count,
                "downloaded_bytes": stats.current_stats.downloaded_bytes,
                "uploaded_bytes": stats.current_stats.uploaded_bytes,
                "files_added": stats.current_stats.files_added
            }

        except TransmissionError as e:
            logger.error(f"Failed to get stats: {e}")
            raise

    def get_completed_torrents(self) -> List[Dict[str, Any]]:
        """
        Get all completed torrents (100% done, seeding or stopped).

        Returns:
            List of completed torrent information
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        try:
            torrents = self._client.get_torrents()

            completed = []
            for torrent in torrents:
                # Check if 100% done and seeding or stopped
                if torrent.percent_done >= 1.0:
                    completed.append({
                        "id": torrent.id,
                        "name": torrent.name,
                        "hash": torrent.hashString,
                        "status": torrent.status,
                        "download_dir": torrent.download_dir,
                        "total_size": torrent.total_size,
                        "date_done": torrent.date_done.isoformat() if torrent.date_done else None,
                        "files": self._get_torrent_files(torrent)
                    })

            return completed

        except TransmissionError as e:
            logger.error(f"Failed to get completed torrents: {e}")
            raise

    def _get_torrent_files(self, torrent) -> List[str]:
        """
        Get list of file paths for a torrent.

        Args:
            torrent: Transmission torrent object

        Returns:
            List of absolute file paths
        """
        files = []
        download_dir = Path(torrent.download_dir)

        for file_info in torrent.get_files():
            file_path = download_dir / file_info.name
            files.append(str(file_path))

        return files
