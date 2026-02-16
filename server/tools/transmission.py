"""MCP tools for Transmission BitTorrent client management."""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from server.transmission import TransmissionClient, is_valid_torrent_reference


logger = logging.getLogger(__name__)


async def add_torrent(
    client: TransmissionClient,
    magnet_or_url: str,
    download_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a torrent via magnet link or .torrent URL.

    Validation:
    - Accept only magnet URIs (magnet:) and explicit .torrent URLs
    - If download_dir is set, it must be under PLEX_INGEST_DIR

    Args:
        client: TransmissionClient instance
        magnet_or_url: Magnet URI or .torrent file URL
        download_dir: Optional download directory (must be under PLEX_INGEST_DIR)

    Returns:
        Dict with torrent information
    """
    if not client.is_connected:
        return {
            "error": "Transmission client not connected. Please check TRANSMISSION_URL configuration."
        }

    # Validate torrent format
    if not is_valid_torrent_reference(magnet_or_url):
        return {
            "error": "Invalid torrent format. Must be a magnet URI (magnet:) or .torrent URL/path"
        }

    # Validate download_dir if provided
    if download_dir:
        ingest_dir = os.getenv("PLEX_INGEST_DIR")
        if not ingest_dir:
            return {
                "error": "PLEX_INGEST_DIR not configured. Cannot validate download directory."
            }

        # Resolve paths and check containment
        ingest_path = Path(ingest_dir).resolve()
        download_path = Path(download_dir).resolve()

        try:
            download_path.relative_to(ingest_path)
        except ValueError:
            return {
                "error": f"Download directory must be under PLEX_INGEST_DIR ({ingest_dir})"
            }

    try:
        result = client.add_torrent(magnet_or_url, download_dir)
        logger.info(f"Added torrent: {result['name']}")
        return result

    except Exception as e:
        logger.error(f"Failed to add torrent: {e}")
        return {"error": str(e)}


async def list_torrents(
    client: TransmissionClient,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List torrents with optional status filter.

    Args:
        client: TransmissionClient instance
        status: Filter by status (downloading/seeding/stopped/all)

    Returns:
        List of torrent information dictionaries
    """
    if not client.is_connected:
        return [{"error": "Transmission client not connected"}]

    try:
        torrents = client.list_torrents(status_filter=status)
        logger.info(f"Listed {len(torrents)} torrents" + (f" (filter: {status})" if status else ""))
        return torrents

    except Exception as e:
        logger.error(f"Failed to list torrents: {e}")
        return [{"error": str(e)}]


async def get_torrent_status(
    client: TransmissionClient,
    torrent_id: int
) -> Dict[str, Any]:
    """
    Get detailed status of a specific torrent.

    Args:
        client: TransmissionClient instance
        torrent_id: Torrent ID

    Returns:
        Dict with detailed torrent information
    """
    if not client.is_connected:
        return {"error": "Transmission client not connected"}

    try:
        status = client.get_torrent_status(torrent_id)
        logger.info(f"Retrieved status for torrent {torrent_id}")
        return status

    except Exception as e:
        logger.error(f"Failed to get torrent status: {e}")
        return {"error": str(e)}


async def pause_torrent(
    client: TransmissionClient,
    torrent_id: int
) -> Dict[str, Any]:
    """
    Pause a torrent download.

    Args:
        client: TransmissionClient instance
        torrent_id: Torrent ID

    Returns:
        Status message
    """
    if not client.is_connected:
        return {"error": "Transmission client not connected"}

    try:
        result = client.pause_torrent(torrent_id)
        logger.info(f"Paused torrent {torrent_id}")
        return result

    except Exception as e:
        logger.error(f"Failed to pause torrent: {e}")
        return {"error": str(e)}


async def resume_torrent(
    client: TransmissionClient,
    torrent_id: int
) -> Dict[str, Any]:
    """
    Resume a paused torrent.

    Args:
        client: TransmissionClient instance
        torrent_id: Torrent ID

    Returns:
        Status message
    """
    if not client.is_connected:
        return {"error": "Transmission client not connected"}

    try:
        result = client.resume_torrent(torrent_id)
        logger.info(f"Resumed torrent {torrent_id}")
        return result

    except Exception as e:
        logger.error(f"Failed to resume torrent: {e}")
        return {"error": str(e)}


async def remove_torrent(
    client: TransmissionClient,
    torrent_id: int,
    delete_data: bool = False
) -> Dict[str, Any]:
    """
    Remove a torrent and optionally delete downloaded data.

    Args:
        client: TransmissionClient instance
        torrent_id: Torrent ID
        delete_data: Also delete downloaded data (default: False)

    Returns:
        Status message
    """
    if not client.is_connected:
        return {"error": "Transmission client not connected"}

    try:
        result = client.remove_torrent(torrent_id, delete_data)
        logger.info(f"Removed torrent {torrent_id} (delete_data={delete_data})")
        return result

    except Exception as e:
        logger.error(f"Failed to remove torrent: {e}")
        return {"error": str(e)}


async def get_transmission_stats(client: TransmissionClient) -> Dict[str, Any]:
    """
    Get Transmission daemon statistics.

    Args:
        client: TransmissionClient instance

    Returns:
        Dict with daemon statistics
    """
    if not client.is_connected:
        return {"error": "Transmission client not connected"}

    try:
        stats = client.get_stats()
        logger.info("Retrieved Transmission statistics")
        return stats

    except Exception as e:
        logger.error(f"Failed to get Transmission stats: {e}")
        return {"error": str(e)}
