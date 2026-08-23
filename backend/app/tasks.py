"""
Background jobs. These functions only ever run inside the `worker`
container, which has HMMER and Foldseek installed and has the
pre-built databases mounted read-only at /data.

The `api` container never imports the subprocess-calling code path
directly — it only enqueues these by import string, so the API image
itself never needs HMMER/Foldseek installed.
"""
import csv
import functools
import os
import re
import subprocess
import tempfile
from pathlib import Path

DATA_DIR = Path("/data")
HMM_DB = DATA_DIR / "hmm" / "evades_profiles.hmm"          # `hmmpress`-ed HMM library
FOLDSEEK_DB = DATA_DIR / "foldseek" / "evades_structures_db"  # `foldseek createdb` output
METADATA_TSV = DATA_DIR / "downloads" / "metadata.tsv"      # curated EVADES protein metadata


@functools.lru_cache(maxsize=1)
def _load_metadata() -> dict[str, dict[str, str]]:
    """protein ID -> {"defence": ..., "moa": ...}, from the same
    metadata.tsv the bulk-download/Explore pages are built from.
    Cheap enough (268 rows) to load fully and cache once."""
    if not METADATA_TSV.exists():
        return {}

    def clean(value: str | None) -> str:
        return value if value not in (None, "", "_") else ""

    with METADATA_TSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return {
            row["ID"]: {
                "defence": clean(row.get("Defences")),
                "moa": clean(row.get("MoA")),
            }
            for row in reader
            if row.get("ID")
        }


def _inhibited_defence(protein_id: str) -> str:
    return _load_metadata().get(protein_id, {}).get("defence", "")


def _moa(protein_id: str) -> str:
    return _load_metadata().get(protein_id, {}).get("moa", "")

# Some source PDBs (e.g. NMR structures) contained many models of the
# same chain. foldseek createdb indexes each model as its own entry,
# e.g. "klca_MODEL_16_A". This pattern strips that suffix back down
# to the base protein name so results can be collapsed per-protein.
MODEL_SUFFIX_RE = re.compile(r"_MODEL_\d+_[A-Za-z0-9]+$")

# TM-score >= 0.5 is the standard structural-biology convention for
# "generally the same fold" (Zhang & Skolnick, 2004); below ~0.17 is
# essentially random similarity.
FOLDSEEK_TM_SCORE_MIN = float(os.environ.get("FOLDSEEK_TM_SCORE_MIN", "0.5"))


def _base_protein_name(target: str) -> str:
    return MODEL_SUFFIX_RE.sub("", target)


def run_hmmsearch(fasta_path: str) -> dict:
    """Run hmmsearch of the query FASTA against the EVADES HMM profile
    database and return parsed hits."""
    fasta_path = Path(fasta_path)
    if not HMM_DB.exists():
        raise RuntimeError(
            f"HMM database not found at {HMM_DB}. "
            "Download it from the EBI FTP and rename to evades_profiles.hmm (see data/README.md)"
        )

    with tempfile.TemporaryDirectory() as tmp:
        domtblout = Path(tmp) / "hits.domtblout"
        cmd = [
            "hmmsearch",
            "--domtblout", str(domtblout),
            "-E", "1e-5",          # e-value cutoff; use instead of --cut_ga since
                                    # not every profile in the library has a
                                    # curated GA (gathering) threshold set
            "--cpu", "2",
            str(HMM_DB),
            str(fasta_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=550)
        if proc.returncode != 0:
            raise RuntimeError(f"hmmsearch failed: {proc.stderr[-2000:]}")

        hits = _parse_domtblout(domtblout)

    return {"tool": "hmmsearch", "hits": hits, "n_hits": len(hits)}


def _parse_domtblout(path: Path) -> list[dict]:
    hits = []
    with path.open() as f:
        for line in f:
            if line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 22:
                continue
            # HMM profiles are named "<protein id>.aln" after the
            # alignment file they were built from — strip that back
            # down to the plain ADP id for display/linking.
            adp = re.sub(r"\.aln$", "", fields[3])
            hits.append({
                "query_name": fields[0],
                "adp": adp,
                "moa": _moa(adp),
                "defence": _inhibited_defence(adp),
                "evalue": float(fields[6]),
                "score": float(fields[7]),
                "hmm_from": int(fields[15]),
                "hmm_to": int(fields[16]),
                "ali_from": int(fields[17]),
                "ali_to": int(fields[18]),
            })
    hits.sort(key=lambda h: h["evalue"])
    return hits


def run_foldseek(pdb_path: str) -> dict:
    """Run foldseek easy-search of the query structure against the
    268-structure EVADES Foldseek database and return parsed hits."""
    pdb_path = Path(pdb_path)
    if not FOLDSEEK_DB.with_suffix("").exists() and not Path(str(FOLDSEEK_DB)).exists():
        raise RuntimeError(
            f"Foldseek database not found at {FOLDSEEK_DB}. "
            "Build it once with: foldseek createdb structures/ evades_structures_db"
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        results_tsv = tmp_path / "results.tsv"
        cmd = [
            "foldseek", "easy-search",
            str(pdb_path),
            str(FOLDSEEK_DB),
            str(results_tsv),
            str(tmp_path / "tmp"),
            "--alignment-type", "1",   # exact TM-align (Kabsch superposition),
                                       # not the fast 3Di/AA estimate — affordable
                                       # at 268 structures, and needed for a
                                       # trustworthy "same fold" TM-score
            "--tmscore-threshold", str(FOLDSEEK_TM_SCORE_MIN),
            # NOTE: do NOT use -e for filtering here. Under
            # --alignment-type 1, Foldseek redefines the "evalue"
            # output field to be (qTMscore+tTMscore)/2 — a TM-score-
            # like value where HIGHER is better, not a real
            # statistical e-value. Passing -e with normal e-value
            # semantics (lower is better) silently filters out all
            # real hits. --tmscore-threshold is the correct filter
            # for this mode.
            "--format-output",
            # No "evalue" or "bits" columns: under --alignment-type 1
            # both are repurposed by Foldseek — evalue becomes
            # (qTM+tTM)/2, bits becomes qTM*100 — neither is the
            # traditional statistic the name implies, and both are
            # redundant with tm_score (alntmscore) and prob, which
            # already convey match quality correctly.
            "query,target,fident,alnlen,prob,alntmscore",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=250)
        if proc.returncode != 0:
            raise RuntimeError(f"foldseek failed: {proc.stderr[-2000:]}")

        hits = []
        if results_tsv.exists():
            with results_tsv.open() as f:
                reader = csv.reader(f, delimiter="\t")
                for row in reader:
                    if len(row) < 6:
                        continue
                    hits.append({
                        "query": row[0],
                        "adp": row[1],
                        "seq_identity": float(row[2]),
                        "aln_len": int(row[3]),
                        "prob": float(row[4]),
                        # TM-score is mathematically bounded to (0, 1];
                        # floating-point rounding on near-perfect
                        # matches can occasionally push the raw value
                        # a hair above 1.0 even with exact TM-align.
                        # Clamp for display — the underlying match is
                        # still valid, just capped at its true ceiling.
                        "tm_score": min(float(row[5]), 1.0),
                    })

        # "Same fold" filter: TM-score >= FOLDSEEK_TM_SCORE_MIN. Already
        # enforced by --tmscore-threshold above at the tool level; this
        # is a belt-and-braces re-check against the alntmscore field.
        # (No e-value filter here: under --alignment-type 1, the
        # "evalue" field means something different — see cmd comment
        # above — so it's not a valid significance filter in this mode.)
        hits = [h for h in hits if h["tm_score"] >= FOLDSEEK_TM_SCORE_MIN]

        # Collapse multi-model proteins (e.g. NMR ensembles indexed as
        # separate "protein_MODEL_N_A" entries) down to one row per
        # protein, keeping only the highest-confidence (prob) model.
        best_by_protein: dict[str, dict] = {}
        for hit in hits:
            base_name = _base_protein_name(hit["adp"])
            hit["adp"] = base_name
            existing = best_by_protein.get(base_name)
            if existing is None or hit["prob"] > existing["prob"]:
                best_by_protein[base_name] = hit

        hits = sorted(best_by_protein.values(), key=lambda h: -h["prob"])
        for hit in hits:
            hit["moa"] = _moa(hit["adp"])
            hit["defence"] = _inhibited_defence(hit["adp"])
        # Reorder so "moa"/"defence" sit right after "adp" (dict field
        # order drives the frontend table's column order).
        hits = [
            {
                "query": h["query"],
                "adp": h["adp"],
                "moa": h["moa"],
                "defence": h["defence"],
                "seq_identity": h["seq_identity"],
                "aln_len": h["aln_len"],
                "prob": h["prob"],
                "tm_score": h["tm_score"],
            }
            for h in hits
        ]

    return {"tool": "foldseek", "hits": hits, "n_hits": len(hits)}