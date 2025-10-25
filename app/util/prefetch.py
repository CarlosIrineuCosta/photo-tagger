from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass(slots=True)
class PrefetchJob:
    """
    Represents the status of a thumbnail prefetch job.
    """

    job_id: str
    paths: List[str]
    overwrite: bool = False
    processed: int = 0
    errors: List[str] = field(default_factory=list)
    status: str = "queued"  # queued | running | complete | error

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "paths": list(self.paths),
            "overwrite": self.overwrite,
            "processed": self.processed,
            "errors": list(self.errors),
            "status": self.status,
        }

    def mark_running(self) -> None:
        if self.status == "queued":
            self.status = "running"

    def mark_complete(self) -> None:
        if self.status != "error":
            self.status = "complete"

    def mark_error(self, message: str) -> None:
        self.status = "error"
        self.errors.append(message)

    @property
    def total(self) -> int:
        return len(self.paths)


class PrefetchManager:
    """
    Thread-safe manager for prefetch jobs. Progress updates are pushed by the worker.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, PrefetchJob] = {}
        self._lock = threading.Lock()

    def create_job(self, paths: Iterable[str], overwrite: bool = False) -> PrefetchJob:
        job_id = uuid.uuid4().hex[:12]
        job = PrefetchJob(job_id=job_id, paths=list(paths), overwrite=overwrite)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[PrefetchJob]:
        with self._lock:
            job = self._jobs.get(job_id)
        return job

    def update_progress(self, job_id: str, processed: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.processed = min(processed, job.total)

    def append_error(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.errors.append(message)
            job.status = "error"

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.mark_running()

    def mark_complete(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.mark_complete()

    def snapshot(self, job_id: str) -> Optional[dict]:
        job = self.get_job(job_id)
        if job is None:
            return None
        return job.to_dict()


__all__ = ["PrefetchJob", "PrefetchManager"]
