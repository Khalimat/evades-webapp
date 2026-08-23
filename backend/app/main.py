"""
EVADES web app — API layer.

Responsibilities:
- Accept uploads (FASTA for HMM search, PDB for structure search)
- Enqueue a background job on Redis/RQ
- Let the frontend poll job status and fetch results
- Serve nothing computational itself — all HMMER/Foldseek execution
  happens in the `worker` container, never here.
"""
import os
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from rq import Queue
from rq.job import Job

from .database import JobRecord, get_session, init_db
from .schemas import JobOut

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FASTA_BYTES = int(os.environ.get("MAX_FASTA_BYTES", 10 * 1024 * 1024))  # 10 MB
MAX_FASTA_SEQUENCES = int(os.environ.get("MAX_FASTA_SEQUENCES", 500))
NUCLEOTIDE_CHARS = set("ACGTUN")

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_conn = Redis.from_url(REDIS_URL)
queue = Queue("default", connection=redis_conn)

app = FastAPI(title="EVADES Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your real frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _save_upload(upload: UploadFile) -> Path:
    job_dir = UPLOAD_DIR / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    dest = job_dir / upload.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


def _save_bytes(content: bytes, filename: str) -> Path:
    job_dir = UPLOAD_DIR / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    dest = job_dir / filename
    dest.write_bytes(content)
    return dest


def validate_protein_fasta(content: bytes) -> None:
    """Reject empty/oversized files, files that aren't valid FASTA, and
    files that look like nucleotide sequences rather than protein —
    all cheap checks that catch the most common mistaken uploads
    before wasting a worker slot running hmmsearch on garbage."""
    if len(content) == 0:
        raise HTTPException(400, "Uploaded file is empty")
    if len(content) > MAX_FASTA_BYTES:
        raise HTTPException(
            400,
            f"File exceeds the {MAX_FASTA_BYTES // (1024 * 1024)} MB limit for FASTA uploads",
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File is not valid text — is this really a FASTA file?")

    if not text.lstrip().startswith(">"):
        raise HTTPException(400, "File doesn't look like FASTA (should start with '>')")

    headers = [line for line in text.splitlines() if line.startswith(">")]
    n_seqs = len(headers)
    if n_seqs == 0:
        raise HTTPException(400, "No sequences found in FASTA file")
    if n_seqs > MAX_FASTA_SEQUENCES:
        raise HTTPException(
            400, f"Too many sequences ({n_seqs}); limit is {MAX_FASTA_SEQUENCES} per upload"
        )

    # Heuristic: real protein sequences use the full 20-letter amino
    # acid alphabet, so they're mostly NOT A/C/G/T/U/N. A file that's
    # overwhelmingly those letters is almost certainly DNA/RNA that
    # was uploaded by mistake.
    seq_chars = "".join(
        line.strip().upper() for line in text.splitlines() if line and not line.startswith(">")
    )
    seq_chars = seq_chars.replace("*", "").replace("-", "")
    if seq_chars:
        nt_fraction = sum(1 for c in seq_chars if c in NUCLEOTIDE_CHARS) / len(seq_chars)
        if nt_fraction > 0.9:
            raise HTTPException(
                400,
                "This looks like a nucleotide (DNA/RNA) sequence, not protein. "
                "The HMM search expects translated protein sequences.",
            )


@app.post("/api/search/hmm", response_model=JobOut)
def search_hmm(fasta: UploadFile = File(...)):
    """Search an uploaded multi-FASTA of protein sequences against the
    EVADES HMM profile database using hmmsearch."""
    if not fasta.filename:
        raise HTTPException(400, "No file provided")

    content = fasta.file.read()
    validate_protein_fasta(content)
    fasta_path = _save_bytes(content, fasta.filename)

    rq_job = queue.enqueue(
        "app.tasks.run_hmmsearch",
        str(fasta_path),
        job_timeout=600,
    )

    with get_session() as session:
        record = JobRecord(
            id=rq_job.id,
            job_type="hmm",
            input_filename=fasta.filename,
            status="queued",
        )
        session.add(record)
        session.commit()

    return JobOut(id=rq_job.id, status="queued", job_type="hmm")


@app.post("/api/search/structure", response_model=JobOut)
def search_structure(pdb: UploadFile = File(...)):
    """Search an uploaded PDB/mmCIF structure against the pre-built
    Foldseek database of the 268 EVADES structures."""
    if not pdb.filename:
        raise HTTPException(400, "No file provided")

    pdb_path = _save_upload(pdb)

    rq_job = queue.enqueue(
        "app.tasks.run_foldseek",
        str(pdb_path),
        job_timeout=300,
    )

    with get_session() as session:
        record = JobRecord(
            id=rq_job.id,
            job_type="structure",
            input_filename=pdb.filename,
            status="queued",
        )
        session.add(record)
        session.commit()

    return JobOut(id=rq_job.id, status="queued", job_type="structure")


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str):
    try:
        rq_job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        raise HTTPException(404, "Job not found")

    status = rq_job.get_status()  # queued | started | finished | failed

    result = None
    error = None
    if status == "finished":
        result = rq_job.result
    elif status == "failed":
        error = str(rq_job.exc_info)[-2000:] if rq_job.exc_info else "Job failed"

    job_type = "unknown"
    with get_session() as session:
        record = session.get(JobRecord, job_id)
        if record:
            job_type = record.job_type
            if record.status != status:
                record.status = status
                session.add(record)
                session.commit()

    return JobOut(
        id=job_id,
        status=status,
        job_type=job_type,
        result=result,
        error=error,
    )