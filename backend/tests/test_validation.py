import pytest
from fastapi import HTTPException

from app.main import validate_protein_fasta

VALID_PROTEIN = (
    b">seq1\n"
    b"MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKA"
    b"LPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWEL\n"
)


def test_rejects_empty_file():
    with pytest.raises(HTTPException) as exc:
        validate_protein_fasta(b"")
    assert exc.value.status_code == 400


def test_rejects_oversized_file(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "MAX_FASTA_BYTES", 10)
    with pytest.raises(HTTPException) as exc:
        validate_protein_fasta(VALID_PROTEIN)
    assert "MB limit" in exc.value.detail


def test_rejects_non_utf8():
    with pytest.raises(HTTPException) as exc:
        validate_protein_fasta(b"\xff\xfe\x00\x01")
    assert exc.value.status_code == 400


def test_rejects_missing_fasta_header():
    with pytest.raises(HTTPException) as exc:
        validate_protein_fasta(b"MKTAYIAKQRQISFVKSHFSRQ\n")
    assert "start with" in exc.value.detail


def test_rejects_too_many_sequences(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "MAX_FASTA_SEQUENCES", 1)
    fasta = b">seq1\nMKT\n>seq2\nMKT\n"
    with pytest.raises(HTTPException) as exc:
        validate_protein_fasta(fasta)
    assert "Too many sequences" in exc.value.detail


def test_rejects_nucleotide_looking_sequence():
    fasta = b">seq1\n" + b"ACGT" * 20 + b"\n"
    with pytest.raises(HTTPException) as exc:
        validate_protein_fasta(fasta)
    assert "nucleotide" in exc.value.detail.lower()


def test_accepts_valid_protein_fasta():
    validate_protein_fasta(VALID_PROTEIN)  # should not raise
