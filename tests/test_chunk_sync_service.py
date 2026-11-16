from types import SimpleNamespace
from unittest.mock import Mock

from app.chunk_sync.chunk_repository import UpsertResult
from app.chunk_sync.service import ChunkSyncService


def test_flush_pending_chunks_when_rows_threshold_reached() -> None:
    service = object.__new__(ChunkSyncService)
    service.config = SimpleNamespace(upsert_batch_size=1000)
    service._upsert_in_batches = Mock(return_value=UpsertResult(inserted=7, updated=3))

    pending_chunks = [{"id": 1}, {"id": 2}]
    total_inserted, total_updated = service._flush_pending_chunks_if_needed(
        pending_chunks=pending_chunks,
        rows_since_flush=1000,
        total_inserted=0,
        total_updated=0,
    )

    assert service._upsert_in_batches.call_count == 1
    assert service._upsert_in_batches.call_args.args == (pending_chunks, 1000)
    assert total_inserted == 7
    assert total_updated == 3
