"""Guards the split between the two structure-data sources introduced
after a real bug: the live Foldseek search DB (`data/foldseek/`) is
built from `data/foldseek_monomer_structures/` (one chain per protein),
while the website's downloads/Explore pages keep using
`generator/assets/structures/EVADES_v1/` — which legitimately contains
multimers/complexes wherever an ADP's defence-protein interaction is
known (predicted bound to that defence protein, to show the actual
mechanism of action), and single chains everywhere else.

Mixing these up previously caused false hits: a multimer entry like
`gp5_9` (predicted in complex with its target, RecBCD) got indexed by
Foldseek per-chain, so a query matching the *embedded RecB chain* —
not gp5_9 itself — was reported as a `gp5_9` hit after chain-name
collapsing. See the gp5_9 / acric5 case history for the real-world
repro.

Both directories are gitignored (large binary data, built locally per
data/README.md) so these tests skip entirely when run against a fresh
checkout without them — they're a local sanity check to run before
syncing new structure data, not part of the CI-run suite.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MONOMER_DIR = REPO_ROOT / "data" / "foldseek_monomer_structures"
MULTIMER_DIR = REPO_ROOT / "generator" / "assets" / "structures" / "EVADES_v1"
METADATA_TSV = REPO_ROOT / "data" / "downloads" / "metadata.tsv"

# Known-multimeric proteins (predicted in complex with a binding
# partner) — the website/download source must keep these as multimers.
KNOWN_MULTIMER_IDS = ["gp5_9", "acric5"]

pytestmark = pytest.mark.skipif(
    not MONOMER_DIR.exists() or not any(MONOMER_DIR.iterdir()),
    reason="data/foldseek_monomer_structures/ not present locally (gitignored data)",
)


def _pdb_chains(path: Path) -> set[str]:
    chains = set()
    with path.open(errors="ignore") as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                chains.add(line[21])
    return chains


def _cif_chains(path: Path) -> set[str]:
    chains = set()
    cols = []
    with path.open(errors="ignore") as f:
        for line in f:
            if line.startswith("_atom_site."):
                cols.append(line.strip().split(".", 1)[1])
                continue
            if line.startswith(("ATOM", "HETATM")):
                fields = line.split()
                if "auth_asym_id" in cols:
                    idx = cols.index("auth_asym_id")
                    if idx < len(fields):
                        chains.add(fields[idx])
    return chains


def _chains(path: Path) -> set[str]:
    return _pdb_chains(path) if path.suffix.lower() == ".pdb" else _cif_chains(path)


def _structure_ids(directory: Path) -> dict[str, Path]:
    files = {}
    for path in directory.iterdir():
        if path.suffix.lower() in (".pdb", ".cif"):
            files[path.stem] = path
    return files


def test_foldseek_monomer_structures_have_all_protein_ids():
    if not METADATA_TSV.exists():
        pytest.skip("data/downloads/metadata.tsv not present locally")
    import csv

    with METADATA_TSV.open(newline="", encoding="utf-8") as f:
        expected_ids = {row["ID"] for row in csv.DictReader(f, delimiter="\t") if row.get("ID")}

    monomer_files = _structure_ids(MONOMER_DIR)
    missing = expected_ids - monomer_files.keys()
    assert not missing, f"missing monomer structure(s) for: {sorted(missing)}"


def test_foldseek_monomer_structures_are_single_chain():
    monomer_files = _structure_ids(MONOMER_DIR)
    assert monomer_files, "expected at least one structure in data/foldseek_monomer_structures/"

    not_single_chain = {}
    for protein_id, path in monomer_files.items():
        chains = _chains(path)
        if len(chains) != 1:
            not_single_chain[protein_id] = sorted(chains)

    assert not not_single_chain, (
        "these entries in data/foldseek_monomer_structures/ are not single-chain "
        f"(the Foldseek DB must be built from monomers only): {not_single_chain}"
    )


@pytest.mark.skipif(not MULTIMER_DIR.exists(), reason="generator/assets/ not present locally")
@pytest.mark.parametrize("protein_id", KNOWN_MULTIMER_IDS)
def test_website_download_source_keeps_multimers(protein_id):
    multimer_files = _structure_ids(MULTIMER_DIR)
    assert protein_id in multimer_files, f"{protein_id} missing from {MULTIMER_DIR}"

    chains = _chains(multimer_files[protein_id])
    assert len(chains) > 1, (
        f"{protein_id} in {MULTIMER_DIR} has only {len(chains)} chain(s) — "
        "expected the multimer/complex used for downloads and Explore pages, "
        "not the Foldseek-only monomer version"
    )
