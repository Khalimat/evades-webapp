import os
import time

import pytest
from fastapi.testclient import TestClient

import app.main as main_module

VALID_PROTEIN = (
    b">seq1\n"
    b"MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKA"
    b"LPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWEL\n"
)


@pytest.fixture
def client():
    # Plain instantiation (no `with`) so the FastAPI startup event — which
    # calls init_db() and would try to reach a real Postgres — never fires.
    return TestClient(main_module.app)


class FakeJob:
    id = "job-123"


class FakeQueue:
    def enqueue(self, *args, **kwargs):
        return FakeJob()


class FakeSession:
    def add(self, record):
        pass

    def commit(self):
        pass

    def get(self, model, record_id):
        return None


class FakeSessionCtx:
    def __enter__(self):
        return FakeSession()

    def __exit__(self, *exc):
        return False


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_search_hmm_rejects_invalid_fasta(client):
    resp = client.post(
        "/api/search/hmm",
        files={"fasta": ("empty.fasta", b"", "text/plain")},
    )
    assert resp.status_code == 400


def test_search_hmm_enqueues_valid_protein_fasta(client, monkeypatch):
    monkeypatch.setattr(main_module, "queue", FakeQueue())
    monkeypatch.setattr(main_module, "get_session", lambda: FakeSessionCtx())

    resp = client.post(
        "/api/search/hmm",
        files={"fasta": ("valid.fasta", VALID_PROTEIN, "text/plain")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "id": "job-123",
        "status": "queued",
        "job_type": "hmm",
        "result": None,
        "error": None,
    }


def test_search_structure_enqueues_upload(client, monkeypatch):
    monkeypatch.setattr(main_module, "queue", FakeQueue())
    monkeypatch.setattr(main_module, "get_session", lambda: FakeSessionCtx())

    resp = client.post(
        "/api/search/structure",
        files={"pdb": ("structure.pdb", b"HEADER    fake pdb\n", "chemical/x-pdb")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "job-123"
    assert body["job_type"] == "structure"


def test_get_job_not_found(client, monkeypatch):
    class FakeJobClass:
        @staticmethod
        def fetch(job_id, connection=None):
            raise Exception("no such job")

    monkeypatch.setattr(main_module, "Job", FakeJobClass)

    resp = client.get("/api/jobs/does-not-exist")

    assert resp.status_code == 404


def test_sweep_stale_uploads_removes_only_dirs_past_the_cutoff(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "UPLOAD_DIR", tmp_path)

    stale = tmp_path / "stale_job"
    stale.mkdir()
    (stale / "q.fasta").write_text(">x\nMKT\n")
    fresh = tmp_path / "fresh_job"
    fresh.mkdir()
    (fresh / "q.fasta").write_text(">x\nMKT\n")

    old = time.time() - 48 * 3600
    os.utime(stale, (old, old))

    removed = main_module.sweep_stale_uploads(max_age_seconds=24 * 3600)

    assert removed == 1
    assert not stale.exists()
    assert fresh.exists()


def test_sweep_stale_uploads_handles_a_missing_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "UPLOAD_DIR", tmp_path / "nope")
    assert main_module.sweep_stale_uploads() == 0


def test_get_job_returns_status(client, monkeypatch):
    class FakeRqJob:
        def get_status(self):
            return "finished"

        result = {"tool": "hmmsearch", "hits": [], "n_hits": 0}
        exc_info = None

    class FakeJobClass:
        @staticmethod
        def fetch(job_id, connection=None):
            return FakeRqJob()

    monkeypatch.setattr(main_module, "Job", FakeJobClass)
    monkeypatch.setattr(main_module, "get_session", lambda: FakeSessionCtx())

    resp = client.get("/api/jobs/job-123")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "finished"
    assert body["result"] == {"tool": "hmmsearch", "hits": [], "n_hits": 0}
