"""File system watcher for automatic media ingestion."""

import asyncio
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
import logging

from server.matcher import MediaMatcher
from server.files import FileManager
from server.history import IngestHistory, IngestStatus


logger = logging.getLogger(__name__)


class FileStabilityChecker:
    """Checks if a file has reached a stable size (no longer being written)."""

    def __init__(self, path: Path, stability_seconds: int = 60):
        """
        Initialize stability checker.

        Args:
            path: Path to file to monitor
            stability_seconds: Seconds file size must remain constant
        """
        self.path = path
        self.stability_seconds = stability_seconds
        self.stable_size: Optional[int] = None
        self.stable_since: Optional[float] = None
        self.is_stable = False

    async def check(self) -> bool:
        """
        Check if file is stable.

        Returns:
            True if file has been stable for required duration
        """
        if not self.path.exists():
            return False

        current_size = self.path.stat().st_size

        if self.stable_size is None:
            # First check - record size
            self.stable_size = current_size
            self.stable_since = time.time()
            return False

        if current_size != self.stable_size:
            # Size changed - reset
            self.stable_size = current_size
            self.stable_since = time.time()
            return False

        # Check if stable long enough
        elapsed = time.time() - self.stable_since
        if elapsed >= self.stability_seconds:
            self.is_stable = True
            return True

        return False


class IngestEventHandler(FileSystemEventHandler):
    """Handles file system events for the ingest watcher."""

    def __init__(self, watcher: 'IngestWatcher'):
        """Initialize event handler with parent watcher reference."""
        self.watcher = watcher
        super().__init__()

    def on_created(self, event: FileCreatedEvent):
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Schedule async handling via event loop
        if self.watcher._loop:
            self.watcher._loop.call_soon_threadsafe(
                asyncio.create_task,
                self.watcher._handle_new_file(file_path)
            )


class IngestWatcher:
    """Watches a directory for new media files and processes them automatically."""

    def __init__(
        self,
        ingest_dir: Path,
        matcher: MediaMatcher,
        file_manager: FileManager,
        history: IngestHistory,
        auto_ingest: bool = False,
        confidence_threshold: float = 0.85,
        stability_seconds: int = 60,
        transmission_client: Optional[Any] = None
    ):
        """
        Initialize ingest watcher.

        Args:
            ingest_dir: Directory to watch for new files
            matcher: MediaMatcher instance for identification
            file_manager: FileManager for file operations
            history: IngestHistory for logging
            auto_ingest: Auto-process high confidence matches
            confidence_threshold: Minimum confidence for auto-processing
            stability_seconds: Seconds to wait for file stability
            transmission_client: Optional TransmissionClient for torrent monitoring
        """
        self.ingest_dir = Path(ingest_dir)
        self.matcher = matcher
        self.file_manager = file_manager
        self.history = history
        self.auto_ingest = auto_ingest
        self.confidence_threshold = confidence_threshold
        self.stability_seconds = stability_seconds
        self.transmission_client = transmission_client

        # Transmission settings
        self.transmission_poll_interval = int(os.getenv("TRANSMISSION_POLL_INTERVAL", "30"))
        self.transmission_auto_remove = os.getenv("TRANSMISSION_AUTO_REMOVE", "false").lower() == "true"

        self.is_running = False
        self.observer: Optional[Observer] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Processing state
        self._processing: Dict[Path, FileStabilityChecker] = {}
        self._pending_queue: Dict[str, Dict[str, Any]] = {}
        self._stability_task: Optional[asyncio.Task] = None
        self._transmission_task: Optional[asyncio.Task] = None

        # Track processed torrent hashes to prevent duplicates
        self._processed_torrent_hashes: Set[str] = set()

    async def start(self):
        """Start watching the ingest directory."""
        if self.is_running:
            logger.warning("Watcher already running")
            return

        # Get event loop for bridging
        self._loop = asyncio.get_event_loop()

        # Start watchdog observer
        event_handler = IngestEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.ingest_dir), recursive=False)
        self.observer.start()

        # Start stability check background task
        self._stability_task = asyncio.create_task(self._stability_check_loop())

        # Start Transmission polling task if client is available
        if self.transmission_client and self.transmission_client.is_connected:
            self._transmission_task = asyncio.create_task(self._transmission_poll_loop())
            logger.info(f"Transmission polling enabled (interval: {self.transmission_poll_interval}s)")

        self.is_running = True
        logger.info(f"Watcher started on {self.ingest_dir}")

    async def stop(self):
        """Stop watching the ingest directory."""
        if not self.is_running:
            return

        # Stop observer
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        # Cancel stability task
        if self._stability_task:
            self._stability_task.cancel()
            try:
                await self._stability_task
            except asyncio.CancelledError:
                pass
            self._stability_task = None

        # Cancel Transmission polling task
        if self._transmission_task:
            self._transmission_task.cancel()
            try:
                await self._transmission_task
            except asyncio.CancelledError:
                pass
            self._transmission_task = None

        self.is_running = False
        self._loop = None
        logger.info("Watcher stopped")

    async def get_status(self) -> Dict[str, Any]:
        """
        Get current watcher status.

        Returns:
            Dictionary with watcher state information
        """
        return {
            "is_running": self.is_running,
            "ingest_dir": str(self.ingest_dir),
            "auto_ingest": self.auto_ingest,
            "confidence_threshold": self.confidence_threshold,
            "stability_seconds": self.stability_seconds,
            "pending_queue_size": len(self._pending_queue),
            "processing_count": len(self._processing)
        }

    async def configure(
        self,
        auto_ingest: Optional[bool] = None,
        confidence_threshold: Optional[float] = None,
        stability_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update watcher configuration.

        Args:
            auto_ingest: Enable/disable auto-processing
            confidence_threshold: New confidence threshold
            stability_seconds: New stability check duration

        Returns:
            Updated configuration
        """
        if auto_ingest is not None:
            self.auto_ingest = auto_ingest

        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold

        if stability_seconds is not None:
            self.stability_seconds = stability_seconds

        return {
            "auto_ingest": self.auto_ingest,
            "confidence_threshold": self.confidence_threshold,
            "stability_seconds": self.stability_seconds
        }

    async def get_pending_queue(self) -> List[Dict[str, Any]]:
        """
        Get all pending queue items.

        Returns:
            List of pending items awaiting review
        """
        return list(self._pending_queue.values())

    async def approve_pending(self, source: str) -> Dict[str, Any]:
        """
        Approve and process a pending queue item.

        Args:
            source: Source file path

        Returns:
            Processing result
        """
        if source not in self._pending_queue:
            return {
                "status": "error",
                "message": f"Item not found in queue: {source}"
            }

        item = self._pending_queue[source]
        source_path = Path(item["source"])

        # Reconstruct match_result
        match_result = {
            "tmdb_id": item["match"]["id"],
            "tmdb_result": item["match"],
            "confidence": item["confidence"],
            "parsed": item.get("parsed", {}),
            "plex_path": item.get("plex_path", "")
        }

        # Build plex path if not in item
        if not match_result["plex_path"]:
            parsed = match_result["parsed"]
            match_result["plex_path"] = await self.matcher.construct_plex_path(
                parsed, item["match"], source_path.name
            )

        # Process the file
        try:
            result = await self._ingest_file(source_path, match_result)

            # Remove from queue
            del self._pending_queue[source]

            return {
                "status": "success",
                "result": result
            }
        except Exception as e:
            logger.error(f"Error approving pending item {source}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def reject_pending(self, source: str) -> Dict[str, Any]:
        """
        Reject and remove a pending queue item.

        Args:
            source: Source file path

        Returns:
            Result status
        """
        if source not in self._pending_queue:
            return {
                "status": "error",
                "message": f"Item not found in queue: {source}"
            }

        del self._pending_queue[source]

        return {
            "status": "success",
            "message": f"Rejected {source}"
        }

    async def _handle_new_file(self, file_path: Path):
        """
        Handle a newly detected file.

        Args:
            file_path: Path to new file
        """
        # Check if valid video file
        if not self.file_manager.is_valid_extension(file_path):
            logger.debug(f"Ignoring file with invalid extension: {file_path}")
            return

        # Add to processing with stability checker
        if file_path not in self._processing:
            checker = FileStabilityChecker(file_path, self.stability_seconds)
            self._processing[file_path] = checker
            logger.info(f"New file detected: {file_path}")

    async def _stability_check_loop(self):
        """Background task that checks file stability."""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds

                # Check all processing files
                stable_files = []
                for file_path, checker in list(self._processing.items()):
                    if await checker.check():
                        stable_files.append(file_path)

                # Process stable files
                for file_path in stable_files:
                    await self._process_stable_file(file_path)
                    del self._processing[file_path]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stability check loop: {e}")

    async def _process_stable_file(self, file_path: Path):
        """
        Process a file that has reached stable size.

        Args:
            file_path: Path to stable file
        """
        logger.info(f"Processing stable file: {file_path}")

        try:
            # Use full matching pipeline
            match_result = await self.matcher.match_media(file_path.name)

            if not match_result:
                logger.warning(f"Could not match {file_path}")
                return

            tmdb_id = match_result["tmdb_id"]
            confidence = match_result["confidence"]
            match = match_result["tmdb_result"]
            parsed = match_result["parsed"]

            # Check for duplicates
            if await self.history.is_duplicate(tmdb_id=tmdb_id):
                logger.info(f"Duplicate detected (TMDb ID: {tmdb_id}), skipping {file_path}")
                return

            # Auto-ingest or queue
            if self.auto_ingest and confidence >= self.confidence_threshold:
                logger.info(f"Auto-ingesting {file_path} (confidence: {confidence:.2f})")
                await self._ingest_file(file_path, match_result)
            else:
                logger.info(f"Queueing {file_path} for review (confidence: {confidence:.2f})")
                self._pending_queue[str(file_path)] = {
                    "source": str(file_path),
                    "match": match,
                    "confidence": confidence,
                    "parsed": parsed
                }

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")

    async def _ingest_file(
        self,
        source_path: Path,
        match_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ingest a file to the media library.

        Args:
            source_path: Source file path
            match_result: Full match result from MediaMatcher

        Returns:
            Ingest result
        """
        try:
            # Extract data from match result
            tmdb_id = match_result["tmdb_id"]
            confidence = match_result["confidence"]
            plex_path = match_result["plex_path"]
            tmdb_result = match_result["tmdb_result"]

            # Determine media type
            media_type = "tv" if "name" in tmdb_result else "movie"

            # Build destination
            destination = self.file_manager.media_root / plex_path.lstrip("/")

            # Copy file
            copied_path = await self.file_manager.copy_file(
                source=source_path,
                destination=destination
            )

            # Log to history
            await self.history.add_record(
                source_path=str(source_path),
                destination_path=str(copied_path),
                status=IngestStatus.SUCCESS,
                tmdb_id=tmdb_id,
                media_type=media_type,
                confidence=confidence
            )

            logger.info(f"Successfully ingested {source_path} -> {copied_path}")

            return {
                "source": str(source_path),
                "destination": str(copied_path),
                "tmdb_id": tmdb_id,
                "confidence": confidence
            }

        except Exception as e:
            # Log failure
            await self.history.add_record(
                source_path=str(source_path),
                destination_path="",
                status=IngestStatus.FAILED,
                tmdb_id=match_result.get("tmdb_id", 0),
                media_type="movie",
                confidence=match_result.get("confidence", 0.0),
                metadata={"error": str(e)}
            )

            logger.error(f"Failed to ingest {source_path}: {e}")
            raise

    async def _transmission_poll_loop(self):
        """Background task that polls Transmission for completed torrents."""
        logger.info("Starting Transmission polling loop")

        while True:
            try:
                await asyncio.sleep(self.transmission_poll_interval)

                if not self.transmission_client or not self.transmission_client.is_connected:
                    logger.warning("Transmission client not connected, skipping poll")
                    continue

                # Get completed torrents
                try:
                    completed_torrents = self.transmission_client.get_completed_torrents()
                except Exception as e:
                    logger.error(f"Error getting completed torrents: {e}")
                    continue

                # Process each completed torrent
                for torrent in completed_torrents:
                    torrent_hash = torrent["hash"]

                    # Skip if already processed
                    if torrent_hash in self._processed_torrent_hashes:
                        continue

                    logger.info(f"Processing completed torrent: {torrent['name']}")

                    # Process all files in the torrent
                    result = await self._process_torrent_files(torrent)

                    # Mark as processed only when all video files reached a terminal state.
                    # Missing files or processing errors should be retried on the next poll.
                    if result["mark_processed"]:
                        self._processed_torrent_hashes.add(torrent_hash)
                    else:
                        logger.info(
                            f"Deferring completion mark for torrent {torrent['name']} "
                            f"(missing={result['missing_count']}, errors={result['error_count']})"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Transmission poll loop: {e}")

        logger.info("Transmission polling loop stopped")

    async def _process_torrent_files(self, torrent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process all video files from a completed torrent.

        Args:
            torrent: Torrent information dict

        Returns:
            Processing result summary and completion marker decision.
        """
        torrent_id = torrent["id"]
        torrent_hash = torrent["hash"]
        torrent_name = torrent["name"]
        files = torrent.get("files", [])

        if not files:
            logger.warning(f"No files found in torrent {torrent_name}")
            return {
                "video_file_count": 0,
                "ingested_count": 0,
                "queued_count": 0,
                "duplicate_count": 0,
                "unmatched_count": 0,
                "missing_count": 0,
                "error_count": 0,
                "mark_processed": True
            }

        video_file_count = 0
        success_count = 0
        queued_count = 0
        duplicate_count = 0
        unmatched_count = 0
        missing_count = 0
        error_count = 0

        for file_path_str in files:
            file_path = Path(file_path_str)

            # Check if valid video file
            if not self.file_manager.is_valid_extension(file_path):
                logger.debug(f"Skipping non-video file: {file_path}")
                continue

            video_file_count += 1

            # Check if file exists
            if not file_path.exists():
                logger.warning(f"File does not exist: {file_path}")
                missing_count += 1
                continue

            try:
                # Use full matching pipeline
                match_result = await self.matcher.match_media(file_path.name)

                if not match_result:
                    logger.warning(f"Could not match {file_path}")
                    unmatched_count += 1
                    continue

                tmdb_id = match_result["tmdb_id"]
                confidence = match_result["confidence"]
                match = match_result["tmdb_result"]
                parsed = match_result["parsed"]

                # Check for duplicates
                if await self.history.is_duplicate(tmdb_id=tmdb_id):
                    logger.info(f"Duplicate detected (TMDb ID: {tmdb_id}), skipping {file_path}")
                    duplicate_count += 1
                    continue

                # Auto-ingest or queue (skip stability wait for Transmission files)
                if self.auto_ingest and confidence >= self.confidence_threshold:
                    logger.info(f"Auto-ingesting {file_path} from torrent (confidence: {confidence:.2f})")

                    # Ingest the file with torrent metadata
                    match_result_copy = match_result.copy()
                    await self._ingest_file_from_torrent(
                        file_path,
                        match_result_copy,
                        torrent_hash
                    )
                    success_count += 1

                else:
                    logger.info(f"Queueing {file_path} for review (confidence: {confidence:.2f})")
                    self._pending_queue[str(file_path)] = {
                        "source": str(file_path),
                        "match": match,
                        "confidence": confidence,
                        "parsed": parsed,
                        "torrent_hash": torrent_hash,
                        "torrent_name": torrent_name
                    }
                    queued_count += 1

            except Exception as e:
                logger.error(f"Error processing {file_path} from torrent: {e}")
                error_count += 1

        logger.info(
            f"Processed {video_file_count} video files from torrent {torrent_name} "
            f"({success_count} ingested, {queued_count} queued, {duplicate_count} duplicates, "
            f"{unmatched_count} unmatched, {missing_count} missing, {error_count} errors)"
        )

        # Mark processed after all video files are handled (ingested, queued, duplicate, or unmatched).
        # Missing files and processing errors are retried in future polls.
        terminal_count = success_count + queued_count + duplicate_count + unmatched_count
        mark_processed = (
            video_file_count == 0 or
            (terminal_count == video_file_count and missing_count == 0 and error_count == 0)
        )

        # Optionally remove torrent only if fully auto-ingested without queued items.
        if (
            self.transmission_auto_remove and
            success_count > 0 and
            queued_count == 0 and
            missing_count == 0 and
            error_count == 0
        ):
            try:
                logger.info(f"Auto-removing torrent {torrent_name} (ID: {torrent_id})")
                self.transmission_client.remove_torrent(torrent_id, delete_data=False)
            except Exception as e:
                logger.error(f"Failed to auto-remove torrent {torrent_id}: {e}")

        return {
            "video_file_count": video_file_count,
            "ingested_count": success_count,
            "queued_count": queued_count,
            "duplicate_count": duplicate_count,
            "unmatched_count": unmatched_count,
            "missing_count": missing_count,
            "error_count": error_count,
            "mark_processed": mark_processed
        }

    async def _ingest_file_from_torrent(
        self,
        source_path: Path,
        match_result: Dict[str, Any],
        torrent_hash: str
    ) -> Dict[str, Any]:
        """
        Ingest a file from a torrent to the media library.

        Args:
            source_path: Source file path
            match_result: Full match result from MediaMatcher
            torrent_hash: Torrent hash for tracking

        Returns:
            Ingest result
        """
        try:
            # Extract data from match result
            tmdb_id = match_result["tmdb_id"]
            confidence = match_result["confidence"]
            plex_path = match_result["plex_path"]
            tmdb_result = match_result["tmdb_result"]

            # Determine media type
            media_type = "tv" if "name" in tmdb_result else "movie"

            # Build destination
            destination = self.file_manager.media_root / plex_path.lstrip("/")

            # Copy file
            copied_path = await self.file_manager.copy_file(
                source=source_path,
                destination=destination
            )

            # Log to history with torrent metadata
            await self.history.add_record(
                source_path=str(source_path),
                destination_path=str(copied_path),
                status=IngestStatus.SUCCESS,
                tmdb_id=tmdb_id,
                media_type=media_type,
                confidence=confidence,
                metadata={"torrent_hash": torrent_hash}
            )

            logger.info(f"Successfully ingested {source_path} -> {copied_path} (torrent)")

            return {
                "source": str(source_path),
                "destination": str(copied_path),
                "tmdb_id": tmdb_id,
                "confidence": confidence,
                "torrent_hash": torrent_hash
            }

        except Exception as e:
            # Log failure with torrent metadata
            await self.history.add_record(
                source_path=str(source_path),
                destination_path="",
                status=IngestStatus.FAILED,
                tmdb_id=match_result.get("tmdb_id", 0),
                media_type="movie",
                confidence=match_result.get("confidence", 0.0),
                metadata={"error": str(e), "torrent_hash": torrent_hash}
            )

            logger.error(f"Failed to ingest {source_path} from torrent: {e}")
            raise
