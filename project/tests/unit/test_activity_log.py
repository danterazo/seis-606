import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from homelab_dashboard import activity_log
from homelab_dashboard.activity_log import ActivityLog


def record(log: ActivityLog, path: str = "/api/status") -> None:
    log.record(method="GET", path=path, status=200, client="127.0.0.1")


def test_retains_newest_complete_records_within_storage_limit(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "logs" / "access.jsonl", max_bytes=512)
    for index in range(30):
        record(log, f"/request/{index}")
        assert log.path.stat().st_size <= log.max_bytes
    entries = log.read()
    assert 0 < len(entries) < 30
    assert [entry["path"] for entry in entries] == [f"/request/{index}" for index in range(30 - len(entries), 30)]
    assert len(log.path.read_bytes().splitlines()) == len(entries)
    assert log.read(limit=1) == entries[-1:]
    assert log.read(limit=0) == []
    assert log.read(limit=-1) == []


def test_oversized_existing_log_is_bounded_on_read_and_next_write(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "access.jsonl", max_bytes=512)
    log.path.write_bytes(b"x" * 100_000 + b'\n{"path":"/retained"}\n')
    assert log.read() == [{"path": "/retained"}]
    record(log)
    assert log.path.stat().st_size <= log.max_bytes
    assert [entry["path"] for entry in log.read()] == ["/retained", "/api/status"]


def test_tail_preserves_record_exactly_on_boundary(tmp_path: Path) -> None:
    data = b'{"path":"/retained"}\n'
    log = ActivityLog(tmp_path / "access.jsonl", max_bytes=len(data))
    log.path.write_bytes(b"discard\n" + data)
    assert log.read() == [{"path": "/retained"}]


def test_compaction_leaves_room_for_subsequent_appends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = ActivityLog(tmp_path / "access.jsonl", max_bytes=512)
    replace = activity_log.os.replace
    replacements: list[Path] = []

    def track_replace(source: Path, destination: Path) -> None:
        replacements.append(destination)
        replace(source, destination)

    monkeypatch.setattr(activity_log.os, "replace", track_replace)
    for index in range(30):
        record(log, f"/request/{index}")
    assert 0 < len(replacements) <= 15
    assert log.path.stat().st_size <= log.max_bytes


def test_corrupt_non_object_and_incomplete_records_are_skipped(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "access.jsonl")
    log.path.write_bytes(b'broken\n\xff\n[]\nnull\n{"path":"/valid"}\n{"partial":')
    assert log.read() == [{"path": "/valid"}]


def test_missing_log_and_clear(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "logs" / "access.jsonl")
    assert log.read() == []
    record(log, '/\u00fe\nquoted"')
    assert log.read()[0]["path"] == '/\u00fe\nquoted"'
    assert len(log.path.read_bytes().splitlines()) == 1
    log.clear()
    assert log.path.stat().st_size == 0
    assert log.read() == []
    record(log)
    assert len(log.read()) == 1


def test_next_write_recovers_from_incomplete_trailing_record(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "access.jsonl")
    log.path.write_bytes(b'{"path":"/valid"}\n{"partial":')
    record(log, "/next")
    assert [entry["path"] for entry in log.read()] == ["/valid", "/next"]


def test_concurrent_writes_remain_complete_and_bounded(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "access.jsonl", max_bytes=512)
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda index: record(log, f"/request/{index}"), range(100)))
    assert log.path.stat().st_size <= log.max_bytes
    entries = log.read()
    assert entries
    assert len(entries) == len(log.path.read_bytes().splitlines())
    assert len({entry["path"] for entry in entries}) == len(entries)


@pytest.mark.parametrize("max_bytes", [0, -1])
def test_invalid_storage_limit_is_rejected(tmp_path: Path, max_bytes: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        ActivityLog(tmp_path / "access.jsonl", max_bytes=max_bytes)


def test_oversized_entry_preserves_existing_log(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "access.jsonl", max_bytes=512)
    record(log)
    before = log.path.read_bytes()
    with pytest.raises(OSError, match="storage limit"):
        record(log, "x" * 1024)
    assert log.path.read_bytes() == before


def test_failed_compaction_preserves_existing_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = ActivityLog(tmp_path / "access.jsonl", max_bytes=200)
    record(log)
    before = log.path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated disk failure")

    monkeypatch.setattr(activity_log.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated disk failure"):
        record(log, "/next")
    assert log.path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [log.path]
    assert json.loads(before)["path"] == "/api/status"


def test_filesystem_errors_are_not_silently_treated_as_empty(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path)
    with pytest.raises(OSError):
        log.read()
    with pytest.raises(OSError):
        record(log)
    with pytest.raises(OSError):
        log.clear()
