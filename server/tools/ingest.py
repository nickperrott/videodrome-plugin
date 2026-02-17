"""Ingest MCP Tools - Integration with FileManager and IngestHistory.

This module provides MCP tools for the ingest workflow:
- list_ingest_files: List files in ingest directory
- ingest_file: Copy or move file to media library
- get_ingest_history: Query ingest history
- check_duplicate: Check for duplicate content
- get_ingest_statistics: Get ingest statistics
"""

from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from server.files import FileManager, FileOperationError, InvalidExtensionError, PathRestrictionError
from server.history import IngestHistory, IngestStatus, IngestRecord
from server.tools import nas as nas_tools


class IngestTools:
    """MCP tools for file ingest operations.

    Attributes:
        file_manager: FileManager instance for file operations
        history: IngestHistory instance for audit logging
    """

    def __init__(
        self,
        media_root: Union[str, Path],
        ingest_dir: Union[str, Path],
        history_db_path: Union[str, Path]
    ):
        """Initialize IngestTools.

        Args:
            media_root: Root directory for Plex media library
            ingest_dir: Directory for incoming files
            history_db_path: Path to SQLite history database
        """
        self.file_manager = FileManager(
            media_root=media_root,
            ingest_dir=ingest_dir
        )
        self.history = IngestHistory(history_db_path)

    async def initialize(self):
        """Initialize history database."""
        await self.history.initialize()

    async def close(self):
        """Close history database connection."""
        await self.history.close()

    async def _ensure_auto_mount(self, path: Union[str, Path]) -> None:
        """Attempt NAS auto-mount when enabled and path is on the configured volume."""
        mount_result = await nas_tools.ensure_media_volume_for_path(path)
        if mount_result.get("attempted") and not mount_result.get("success", False):
            raise FileOperationError(
                f"Auto-mount failed for {path}: {mount_result.get('error', 'unknown error')}"
            )

    async def list_ingest_files(
        self,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """List video files in ingest directory.

        Args:
            recursive: If True, search subdirectories

        Returns:
            Dictionary with success status and list of file paths
        """
        try:
            await self._ensure_auto_mount(self.file_manager.ingest_dir)
            files = self.file_manager.list_files(
                self.file_manager.ingest_dir,
                recursive=recursive
            )

            return {
                "success": True,
                "files": [str(f) for f in files],
                "count": len(files)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def ingest_file(
        self,
        source_path: str,
        destination_path: str,
        tmdb_id: Optional[int] = None,
        media_type: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        operation: str = "move"
    ) -> Dict[str, Any]:
        """Ingest a file into the media library.

        Args:
            source_path: Source file path
            destination_path: Destination file path
            tmdb_id: TMDb ID (optional)
            media_type: Media type (movie/tv) (optional)
            confidence: Match confidence score (optional)
            metadata: Additional metadata (optional)
            operation: Operation type ('copy' or 'move')

        Returns:
            Dictionary with success status and record ID
        """
        source = Path(source_path)
        dest = Path(destination_path)

        # Create pending record first
        record_id = await self.history.add_record(
            source_path=source,
            destination_path=dest,
            status=IngestStatus.PENDING,
            tmdb_id=tmdb_id,
            media_type=media_type,
            confidence=confidence,
            metadata=metadata
        )

        try:
            await self._ensure_auto_mount(source)
            await self._ensure_auto_mount(dest)

            # Perform file operation
            if operation == "copy":
                result_path = self.file_manager.copy_file(source, dest)
            else:  # move
                result_path = self.file_manager.move_file(source, dest)

            # Update record to success
            await self.history.update_record(
                record_id,
                status=IngestStatus.SUCCESS
            )

            return {
                "success": True,
                "destination": str(result_path),
                "record_id": record_id
            }

        except (InvalidExtensionError, PathRestrictionError, FileOperationError) as e:
            # Update record to failed
            await self.history.update_record(
                record_id,
                status=IngestStatus.FAILED,
                error_message=str(e)
            )

            return {
                "success": False,
                "error": str(e),
                "record_id": record_id
            }

    async def get_ingest_history(
        self,
        status: Optional[str] = None,
        tmdb_id: Optional[int] = None,
        media_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get ingest history with optional filters.

        Args:
            status: Filter by status (success/failed/pending)
            tmdb_id: Filter by TMDb ID
            media_type: Filter by media type
            limit: Maximum number of records to return

        Returns:
            Dictionary with success status and list of records
        """
        try:
            # Convert status string to enum
            status_enum = None
            if status:
                status_enum = IngestStatus(status)

            # Query records
            if limit:
                records = await self.history.get_recent_records(limit=limit)
                # Apply filters manually if needed
                if status_enum or tmdb_id or media_type:
                    all_records = await self.history.query_records(
                        status=status_enum,
                        tmdb_id=tmdb_id,
                        media_type=media_type
                    )
                    records = all_records[:limit]
            else:
                if status_enum or tmdb_id or media_type:
                    records = await self.history.query_records(
                        status=status_enum,
                        tmdb_id=tmdb_id,
                        media_type=media_type
                    )
                else:
                    records = await self.history.get_all_records()

            # Convert records to dictionaries
            record_dicts = []
            for record in records:
                record_dicts.append({
                    "id": record.id,
                    "timestamp": record.timestamp.isoformat(),
                    "source_path": record.source_path,
                    "destination_path": record.destination_path,
                    "status": record.status.value,
                    "tmdb_id": record.tmdb_id,
                    "media_type": record.media_type,
                    "confidence": record.confidence,
                    "metadata": record.metadata,
                    "error_message": record.error_message
                })

            return {
                "success": True,
                "records": record_dicts,
                "count": len(record_dicts)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def check_duplicate(
        self,
        tmdb_id: Optional[int] = None,
        source_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check if content has already been ingested.

        Args:
            tmdb_id: TMDb ID to check
            source_path: Source path to check

        Returns:
            Dictionary with duplicate status and existing records
        """
        try:
            is_dup = await self.history.is_duplicate(
                tmdb_id=tmdb_id,
                source_path=source_path,
                exclude_failed=True
            )

            # Get existing records if duplicate
            existing_records = []
            if is_dup:
                if tmdb_id:
                    records = await self.history.query_records(tmdb_id=tmdb_id)
                elif source_path:
                    all_records = await self.history.get_all_records()
                    records = [r for r in all_records if r.source_path == source_path]
                else:
                    records = []

                # Filter out failed records
                records = [r for r in records if r.status != IngestStatus.FAILED]

                for record in records:
                    existing_records.append({
                        "id": record.id,
                        "timestamp": record.timestamp.isoformat(),
                        "destination_path": record.destination_path,
                        "status": record.status.value
                    })

            return {
                "is_duplicate": is_dup,
                "existing_records": existing_records
            }

        except Exception as e:
            return {
                "is_duplicate": False,
                "error": str(e),
                "existing_records": []
            }

    async def get_statistics(self) -> Dict[str, Any]:
        """Get ingest statistics.

        Returns:
            Dictionary with success status and statistics
        """
        try:
            stats = await self.history.get_statistics()

            return {
                "success": True,
                "statistics": stats
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get MCP tool definitions for all ingest tools.

        Returns:
            List of tool definition dictionaries
        """
        return [
            {
                "name": "list_ingest_files",
                "description": "List video files in the ingest directory waiting to be processed",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "recursive": {
                            "type": "boolean",
                            "description": "Search subdirectories recursively",
                            "default": False
                        }
                    }
                }
            },
            {
                "name": "ingest_file",
                "description": "Ingest a file into the Plex media library by copying or moving it",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_path": {
                            "type": "string",
                            "description": "Path to source file in ingest directory"
                        },
                        "destination_path": {
                            "type": "string",
                            "description": "Destination path in media library"
                        },
                        "tmdb_id": {
                            "type": "integer",
                            "description": "TMDb ID for the media (optional)"
                        },
                        "media_type": {
                            "type": "string",
                            "description": "Media type: 'movie' or 'tv' (optional)"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Match confidence score 0-1 (optional)"
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata (optional)"
                        },
                        "operation": {
                            "type": "string",
                            "description": "Operation type: 'copy' or 'move'",
                            "enum": ["copy", "move"],
                            "default": "move"
                        }
                    },
                    "required": ["source_path", "destination_path"]
                }
            },
            {
                "name": "get_ingest_history",
                "description": "Query ingest operation history with optional filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Filter by status",
                            "enum": ["success", "failed", "pending"]
                        },
                        "tmdb_id": {
                            "type": "integer",
                            "description": "Filter by TMDb ID"
                        },
                        "media_type": {
                            "type": "string",
                            "description": "Filter by media type"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of records to return"
                        }
                    }
                }
            },
            {
                "name": "check_duplicate",
                "description": "Check if content has already been ingested to prevent duplicates",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tmdb_id": {
                            "type": "integer",
                            "description": "TMDb ID to check"
                        },
                        "source_path": {
                            "type": "string",
                            "description": "Source path to check"
                        }
                    }
                }
            },
            {
                "name": "get_ingest_statistics",
                "description": "Get statistics about ingest operations",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]


# Convenience functions for MCP tool handler registration
# These accept the raw file_manager and history objects that main.py holds,
# matching the calling convention in main.py.

async def list_ingest_files(file_manager, recursive: bool = False):
    """MCP tool handler for list_ingest_files."""
    try:
        files = file_manager.list_files(file_manager.ingest_dir, recursive=recursive)
        return {"success": True, "files": [str(f) for f in files], "count": len(files)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def ingest_file(
    file_manager,
    history,
    source_path: str,
    destination_path: str,
    tmdb_id: Optional[int] = None,
    media_type: Optional[str] = None,
    confidence: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    operation: str = "copy"
):
    """MCP tool handler for ingest_file."""
    source = Path(source_path)
    dest = Path(destination_path)
    record_id = await history.add_record(
        source_path=source,
        destination_path=dest,
        status=IngestStatus.PENDING,
        tmdb_id=tmdb_id,
        media_type=media_type,
        confidence=confidence,
        metadata=metadata
    )
    try:
        if operation == "move":
            result_path = file_manager.move_file(source, dest)
        else:
            result_path = file_manager.copy_file(source, dest)
        await history.update_record(record_id, status=IngestStatus.SUCCESS)
        return {"success": True, "destination": str(result_path), "record_id": record_id}
    except (InvalidExtensionError, PathRestrictionError, FileOperationError) as e:
        await history.update_record(record_id, status=IngestStatus.FAILED, error_message=str(e))
        return {"success": False, "error": str(e), "record_id": record_id}
    except Exception as e:
        await history.update_record(record_id, status=IngestStatus.FAILED, error_message=str(e))
        return {"success": False, "error": str(e), "record_id": record_id}


async def get_ingest_history(
    history,
    status: Optional[str] = None,
    tmdb_id: Optional[int] = None,
    media_type: Optional[str] = None,
    limit: Optional[int] = 50
):
    """MCP tool handler for get_ingest_history."""
    status_enum = None
    if status:
        try:
            status_enum = IngestStatus(status.upper())
        except ValueError:
            pass
    records = await history.query_records(
        status=status_enum,
        tmdb_id=tmdb_id,
        media_type=media_type
    )
    if limit:
        records = records[:limit]
    return [
        {
            "id": r.id,
            "source_path": r.source_path,
            "destination_path": r.destination_path,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "tmdb_id": r.tmdb_id,
            "media_type": r.media_type,
            "confidence": r.confidence,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in records
    ]


async def check_duplicate(
    history,
    tmdb_id: Optional[int] = None,
    source_path: Optional[str] = None
):
    """MCP tool handler for check_duplicate."""
    is_dup = await history.is_duplicate(tmdb_id=tmdb_id, source_path=source_path)
    return {"is_duplicate": is_dup, "tmdb_id": tmdb_id, "source_path": source_path}


async def get_ingest_statistics(history):
    """MCP tool handler for get_ingest_statistics."""
    try:
        stats = await history.get_statistics()
        return {"success": True, **stats}
    except Exception as e:
        return {"success": False, "error": str(e)}
