from __future__ import annotations

from app.util.prefetch import PrefetchManager, PrefetchJob


def test_create_job_generates_id():
    manager = PrefetchManager()
    job = manager.create_job(["a.jpg", "b.jpg"], overwrite=True)
    assert isinstance(job, PrefetchJob)
    assert job.job_id
    assert job.paths == ["a.jpg", "b.jpg"]
    assert job.overwrite is True
    assert job.status == "queued"


def test_progress_and_status_updates():
    manager = PrefetchManager()
    job = manager.create_job(["a", "b", "c"])

    manager.mark_running(job.job_id)
    snapshot = manager.snapshot(job.job_id)
    assert snapshot["status"] == "running"

    manager.update_progress(job.job_id, 2)
    snapshot = manager.snapshot(job.job_id)
    assert snapshot["processed"] == 2

    manager.append_error(job.job_id, "failed")
    snapshot = manager.snapshot(job.job_id)
    assert snapshot["status"] == "error"
    assert snapshot["errors"] == ["failed"]

    manager.mark_complete(job.job_id)
    snapshot = manager.snapshot(job.job_id)
    # once in error, status stays error
    assert snapshot["status"] == "error"


def test_mark_complete_success_path():
    manager = PrefetchManager()
    job = manager.create_job(["a", "b"])
    manager.mark_running(job.job_id)
    manager.update_progress(job.job_id, 2)
    manager.mark_complete(job.job_id)
    snapshot = manager.snapshot(job.job_id)
    assert snapshot["status"] == "complete"
    assert snapshot["processed"] == 2
