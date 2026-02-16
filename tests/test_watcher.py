"""Tests for IngestWatcher file system monitoring."""

import pytest
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from server.watcher import IngestWatcher, FileStabilityChecker
from server.matcher import MediaMatcher
from server.files import FileManager
from server.history import IngestHistory, IngestStatus
from server.tmdb_cache import TMDbCache


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
async def matcher(temp_db):
    """Create MediaMatcher with initialized cache."""
    cache = TMDbCache(db_path=temp_db)
    await cache.initialize()
    return MediaMatcher(tmdb_api_key="test", cache=cache)


@pytest.fixture
def file_manager(temp_media_root, temp_ingest_dir):
    """Create FileManager instance."""
    return FileManager(
        media_root=temp_media_root,
        ingest_dir=temp_ingest_dir
    )


@pytest.fixture
async def history_db(temp_db):
    """Create initialized IngestHistory."""
    history = IngestHistory(db_path=temp_db)
    await history.initialize()
    return history


# =============================================================================
# FileStabilityChecker Tests
# =============================================================================

@pytest.mark.asyncio
async def test_stability_checker_initialization(sample_video_file):
    """Test FileStabilityChecker initializes correctly."""
    checker = FileStabilityChecker(sample_video_file, stability_seconds=5)
    assert checker.path == sample_video_file
    assert checker.stability_seconds == 5
    assert checker.stable_size is None
    assert not checker.is_stable


@pytest.mark.asyncio
async def test_stability_checker_stable_file(sample_video_file):
    """Test stability check passes for file with constant size."""
    checker = FileStabilityChecker(sample_video_file, stability_seconds=1)

    # Initial check
    is_stable = await checker.check()
    assert is_stable is False  # First check always returns False

    # Wait for stability period plus a bit
    await asyncio.sleep(1.2)

    # Second check after time passes
    is_stable = await checker.check()
    assert is_stable is True
    assert checker.stable_size == sample_video_file.stat().st_size


@pytest.mark.asyncio
async def test_stability_checker_changing_file(temp_ingest_dir):
    """Test stability check fails for file with changing size."""
    test_file = temp_ingest_dir / "growing.mkv"
    test_file.write_text("content1")

    checker = FileStabilityChecker(test_file, stability_seconds=1)

    # First check
    await checker.check()

    # Simulate file growth
    test_file.write_text("content1 plus more data")

    # Second check should reset
    is_stable = await checker.check()
    assert is_stable is False


@pytest.mark.asyncio
async def test_stability_checker_missing_file(temp_ingest_dir):
    """Test stability check handles missing file."""
    missing_file = temp_ingest_dir / "nonexistent.mkv"
    checker = FileStabilityChecker(missing_file, stability_seconds=1)

    is_stable = await checker.check()
    assert is_stable is False


# =============================================================================
# IngestWatcher Tests
# =============================================================================

@pytest.mark.asyncio
async def test_watcher_initialization(temp_ingest_dir, matcher, file_manager, history_db):
    """Test IngestWatcher initializes correctly."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    assert watcher.ingest_dir == temp_ingest_dir
    assert watcher.matcher == matcher
    assert watcher.file_manager == file_manager
    assert watcher.history == history_db
    assert watcher.auto_ingest is False
    assert watcher.confidence_threshold == 0.85
    assert watcher.stability_seconds == 60
    assert not watcher.is_running


@pytest.mark.asyncio
async def test_watcher_start_stop(temp_ingest_dir, matcher, file_manager, history_db):
    """Test starting and stopping the watcher."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    # Start watcher
    await watcher.start()
    assert watcher.is_running
    assert watcher.observer is not None
    assert watcher.observer.is_alive()

    # Stop watcher
    await watcher.stop()
    assert not watcher.is_running
    assert watcher.observer is None


@pytest.mark.asyncio
async def test_watcher_get_status(temp_ingest_dir, matcher, file_manager, history_db):
    """Test getting watcher status."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    status = await watcher.get_status()
    assert status["is_running"] is False
    assert status["ingest_dir"] == str(temp_ingest_dir)
    assert status["auto_ingest"] is False
    assert status["confidence_threshold"] == 0.85
    assert status["pending_queue_size"] == 0
    assert status["processing_count"] == 0


@pytest.mark.asyncio
async def test_watcher_handle_new_file(temp_ingest_dir, matcher, file_manager, history_db):
    """Test handling a new file event."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    # Create test file
    test_file = temp_ingest_dir / "Inception.2010.1080p.mkv"
    test_file.write_text("test content")

    # Handle new file
    await watcher._handle_new_file(test_file)

    # Should be in processing (stability check)
    assert test_file in watcher._processing


@pytest.mark.asyncio
async def test_watcher_auto_ingest_high_confidence(temp_ingest_dir, matcher, file_manager, history_db, mock_tmdb_movie_result):
    """Test auto-ingest for high confidence match."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db,
        auto_ingest=True,
        confidence_threshold=0.8
    )

    # Mock match_media
    with patch.object(matcher, 'match_media', new_callable=AsyncMock) as mock_match:
        mock_match.return_value = {
            "tmdb_id": 27205,
            "tmdb_result": mock_tmdb_movie_result,
            "confidence": 0.95,
            "plex_path": "/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv",
            "parsed": {"title": "Inception", "year": 2010}
        }

        # Mock file copy
        with patch.object(file_manager, 'copy_file', new_callable=AsyncMock) as mock_copy:
            mock_copy.return_value = Path("/media/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv")

            # Create test file
            test_file = temp_ingest_dir / "Inception.2010.1080p.mkv"
            test_file.write_text("test content")

            # Process stable file
            await watcher._process_stable_file(test_file)

            # Should auto-copy due to high confidence
            assert mock_copy.called


@pytest.mark.asyncio
async def test_watcher_queue_low_confidence(temp_ingest_dir, matcher, file_manager, history_db, mock_tmdb_movie_result):
    """Test queueing for low confidence match."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db,
        auto_ingest=True,
        confidence_threshold=0.95  # Very high threshold
    )

    # Mock match_media with lower confidence
    with patch.object(matcher, 'match_media', new_callable=AsyncMock) as mock_match:
        mock_match.return_value = {
            "tmdb_id": 27205,
            "tmdb_result": mock_tmdb_movie_result,
            "confidence": 0.75,  # Below threshold
            "plex_path": "/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv",
            "parsed": {"title": "Inception"}
        }

        # Create test file
        test_file = temp_ingest_dir / "Inception.mkv"  # Missing year = lower confidence
        test_file.write_text("test content")

        # Process stable file
        await watcher._process_stable_file(test_file)

        # Should be in pending queue
        queue = await watcher.get_pending_queue()
        assert len(queue) > 0


@pytest.mark.asyncio
async def test_watcher_approve_pending(temp_ingest_dir, matcher, file_manager, history_db, mock_tmdb_movie_result):
    """Test approving a pending queue item."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    # Add item to pending queue
    test_file = temp_ingest_dir / "test.mkv"
    test_file.write_text("test")

    watcher._pending_queue[str(test_file)] = {
        "source": str(test_file),
        "match": mock_tmdb_movie_result,
        "confidence": 0.75,
        "parsed": {"title": "Test"},
        "plex_path": "/Movies/Test (2020) {tmdb-27205}/Test (2020) {tmdb-27205}.mkv"
    }

    # Mock file copy
    with patch.object(file_manager, 'copy_file', new_callable=AsyncMock) as mock_copy:
        mock_copy.return_value = Path("/media/Movies/test/test.mkv")

        # Approve
        result = await watcher.approve_pending(str(test_file))

        assert result["status"] == "success"
        assert mock_copy.called
        assert str(test_file) not in watcher._pending_queue


@pytest.mark.asyncio
async def test_watcher_reject_pending(temp_ingest_dir, matcher, file_manager, history_db):
    """Test rejecting a pending queue item."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    # Add item to pending queue
    test_file = temp_ingest_dir / "test.mkv"
    watcher._pending_queue[str(test_file)] = {
        "source": str(test_file),
        "match": {"id": 123},
        "confidence": 0.75
    }

    # Reject
    result = await watcher.reject_pending(str(test_file))

    assert result["status"] == "success"
    assert str(test_file) not in watcher._pending_queue


@pytest.mark.asyncio
async def test_watcher_ignore_invalid_extensions(temp_ingest_dir, matcher, file_manager, history_db):
    """Test watcher ignores files with invalid extensions."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    # Create invalid file
    invalid_file = temp_ingest_dir / "test.txt"
    invalid_file.write_text("test")

    # Should ignore
    await watcher._handle_new_file(invalid_file)
    assert invalid_file not in watcher._processing


@pytest.mark.asyncio
async def test_watcher_configure(temp_ingest_dir, matcher, file_manager, history_db):
    """Test configuring watcher settings."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    # Configure
    config = await watcher.configure(
        auto_ingest=True,
        confidence_threshold=0.9,
        stability_seconds=30
    )

    assert config["auto_ingest"] is True
    assert config["confidence_threshold"] == 0.9
    assert config["stability_seconds"] == 30
    assert watcher.auto_ingest is True
    assert watcher.confidence_threshold == 0.9
    assert watcher.stability_seconds == 30


@pytest.mark.asyncio
async def test_watcher_get_pending_queue(temp_ingest_dir, matcher, file_manager, history_db, mock_tmdb_movie_result):
    """Test getting pending queue items."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    # Add items to queue
    watcher._pending_queue["file1.mkv"] = {
        "source": "file1.mkv",
        "match": mock_tmdb_movie_result,
        "confidence": 0.75
    }
    watcher._pending_queue["file2.mkv"] = {
        "source": "file2.mkv",
        "match": mock_tmdb_movie_result,
        "confidence": 0.80
    }

    queue = await watcher.get_pending_queue()
    assert len(queue) == 2
    assert all("source" in item for item in queue)
    assert all("confidence" in item for item in queue)


@pytest.mark.asyncio
async def test_watcher_stability_background_task(temp_ingest_dir, matcher, file_manager, history_db):
    """Test that stability check runs in background."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db,
        stability_seconds=1
    )

    # Create test file
    test_file = temp_ingest_dir / "test.mkv"
    test_file.write_text("test")

    # Start watcher
    await watcher.start()

    # Add file to processing
    await watcher._handle_new_file(test_file)

    # Wait for stability task
    await asyncio.sleep(2)

    # Stop watcher
    await watcher.stop()


@pytest.mark.asyncio
async def test_watcher_duplicate_detection(temp_ingest_dir, matcher, file_manager, history_db, mock_tmdb_movie_result):
    """Test duplicate detection prevents re-ingesting."""
    # Add existing record
    await history_db.add_record(
        source_path="/ingest/old.mkv",
        destination_path="/media/Movies/test.mkv",
        status=IngestStatus.SUCCESS,
        tmdb_id=27205,
        media_type="movie",
        confidence=0.95
    )

    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db,
        auto_ingest=True
    )

    # Mock match_media
    with patch.object(matcher, 'match_media', new_callable=AsyncMock) as mock_match:
        mock_match.return_value = {
            "tmdb_id": 27205,
            "tmdb_result": mock_tmdb_movie_result,
            "confidence": 0.95,
            "plex_path": "/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv",
            "parsed": {"title": "Inception", "year": 2010}
        }

        # Mock file copy - should NOT be called
        with patch.object(file_manager, 'copy_file', new_callable=AsyncMock) as mock_copy:
            # Create test file
            test_file = temp_ingest_dir / "Inception.2010.mkv"
            test_file.write_text("test")

            # Process
            await watcher._process_stable_file(test_file)

            # Should NOT copy (duplicate detected)
            assert not mock_copy.called


@pytest.mark.asyncio
async def test_process_torrent_files_missing_file_not_marked_processed(
    temp_ingest_dir, matcher, file_manager, history_db
):
    """Missing torrent files should keep the torrent eligible for retry."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    missing_file = temp_ingest_dir / "missing-file.mkv"
    result = await watcher._process_torrent_files({
        "id": 1,
        "hash": "missing-hash",
        "name": "Missing Torrent",
        "files": [str(missing_file)]
    })

    assert result["missing_count"] == 1
    assert result["mark_processed"] is False


@pytest.mark.asyncio
async def test_process_torrent_files_empty_list_marked_processed(
    temp_ingest_dir, matcher, file_manager, history_db
):
    """Empty torrent file lists are terminal and should be marked processed."""
    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db
    )

    result = await watcher._process_torrent_files({
        "id": 10,
        "hash": "empty-hash",
        "name": "Empty Torrent",
        "files": []
    })

    assert result["video_file_count"] == 0
    assert result["mark_processed"] is True


@pytest.mark.asyncio
async def test_process_torrent_files_no_auto_remove_when_queued(
    temp_ingest_dir, matcher, file_manager, history_db, mock_tmdb_movie_result
):
    """Queued torrent files must not trigger auto-remove."""
    transmission_client = MagicMock()
    transmission_client.remove_torrent = MagicMock()

    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db,
        auto_ingest=True,
        confidence_threshold=0.99,
        transmission_client=transmission_client
    )
    watcher.transmission_auto_remove = True

    test_file = temp_ingest_dir / "queued-file.mkv"
    test_file.write_text("test content")

    with patch.object(matcher, "match_media", new_callable=AsyncMock) as mock_match:
        mock_match.return_value = {
            "tmdb_id": 27205,
            "tmdb_result": mock_tmdb_movie_result,
            "confidence": 0.80,
            "plex_path": "/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv",
            "parsed": {"title": "Inception", "year": 2010}
        }

        result = await watcher._process_torrent_files({
            "id": 2,
            "hash": "queued-hash",
            "name": "Queued Torrent",
            "files": [str(test_file)]
        })

    assert result["queued_count"] == 1
    assert result["mark_processed"] is True
    transmission_client.remove_torrent.assert_not_called()


@pytest.mark.asyncio
async def test_transmission_poll_loop_does_not_mark_processed_when_retry_needed(
    temp_ingest_dir, matcher, file_manager, history_db
):
    """Torrent hash should not be marked processed when processing asks for retry."""
    transmission_client = MagicMock()
    transmission_client.is_connected = True
    transmission_client.get_completed_torrents.return_value = [{
        "id": 3,
        "hash": "retry-hash",
        "name": "Retry Torrent",
        "files": []
    }]

    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db,
        transmission_client=transmission_client
    )

    with patch.object(
        watcher,
        "_process_torrent_files",
        new=AsyncMock(return_value={
            "mark_processed": False,
            "missing_count": 1,
            "error_count": 0
        })
    ):
        with patch("server.watcher.asyncio.sleep", new=AsyncMock(side_effect=[None, asyncio.CancelledError])):
            await watcher._transmission_poll_loop()

    assert "retry-hash" not in watcher._processed_torrent_hashes


@pytest.mark.asyncio
async def test_transmission_poll_loop_marks_processed_when_terminal(
    temp_ingest_dir, matcher, file_manager, history_db
):
    """Torrent hash should be marked processed when processing is terminal."""
    transmission_client = MagicMock()
    transmission_client.is_connected = True
    transmission_client.get_completed_torrents.return_value = [{
        "id": 4,
        "hash": "terminal-hash",
        "name": "Terminal Torrent",
        "files": []
    }]

    watcher = IngestWatcher(
        ingest_dir=temp_ingest_dir,
        matcher=matcher,
        file_manager=file_manager,
        history=history_db,
        transmission_client=transmission_client
    )

    with patch.object(
        watcher,
        "_process_torrent_files",
        new=AsyncMock(return_value={
            "mark_processed": True,
            "missing_count": 0,
            "error_count": 0
        })
    ):
        with patch("server.watcher.asyncio.sleep", new=AsyncMock(side_effect=[None, asyncio.CancelledError])):
            await watcher._transmission_poll_loop()

    assert "terminal-hash" in watcher._processed_torrent_hashes
