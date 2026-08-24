#!/usr/bin/env python3
"""
Build real two-chain (query + target) full-atom aligned structures,
using the rotation/translation matrix Foldseek already computed
(TM-align, captured via the u/t columns in
assets/euk_virus_homolog_search/results.tsv) applied to the target's
real full-atom predicted structure (fetched by
fetch_euk_virus_target_structures.py). This is the same underlying
alignment a tool like FATCAT would produce, without needing FATCAT -
Foldseek already did the actual alignment; this just applies its
output transform to the target's real structure instead of Foldseek's
own Calpha-only --format-mode 5 output (which also doesn't include the
query in the same file).

Foldseek's own docs: "we apply U and T to the target to superposition
it onto the query structure" - so the query is written unmodified
(its own chain, or the relevant single chain if it's one chain of a
multi-chain query), and the target's every atom is transformed and
written as a second chain.

For the small number of targets not resolvable by
fetch_euk_virus_target_structures.py (a handful of PART{N}_-prefixed
polyprotein fragments not present in the Nomburg et al. supplementary
table - see that script's "Unresolved" output), falls back to copying
Foldseek's own Calpha-only structure_alignments output for that hit if
available (--fallback-dir), otherwise the hit just gets no structure.

Usage (from generator/):
    ./.venv/bin/python pipeline/bin/build_euk_virus_aligned_structures.py \\
        --tsv assets/euk_virus_homolog_search/results.tsv \\
        --query-structures-dir assets/structures/EVADES_v1 \\
        --target-cif-dir work/euk_virus_target_structures_cif \\
        --out-dir work/euk_virus_aligned_structures
"""
import argparse
import csv
import shutil
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from Bio.PDB import MMCIFParser, PDBParser, PDBIO, Structure, Model, Chain
from Bio.PDB.PDBExceptions import PDBConstructionWarning

warnings.simplefilter("ignore", PDBConstructionWarning)

COLUMNS = [
    "query", "target", "fident", "alnlen", "qstart", "qend", "tstart", "tend",
    "prob", "alntmscore", "qtmscore", "ttmscore", "u", "t", "qaln", "taln", "lddt",
]


def read_hits(tsv_path: Path) -> List[Dict]:
    hits = []
    with tsv_path.open() as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < len(COLUMNS):
                continue
            hits.append(dict(zip(COLUMNS, row)))
    return hits


def load_structure(path: Path):
    if path.suffix.lower() == ".cif":
        parser = MMCIFParser(QUIET=True)
    else:
        parser = PDBParser(QUIET=True)
    return parser.get_structure(path.stem, str(path))


def find_query_file(query_structures_dir: Path, base_query: str) -> Optional[Path]:
    for ext in (".cif", ".pdb"):
        p = query_structures_dir / f"{base_query}{ext}"
        if p.exists():
            return p
    return None


def base_query_and_chain(query: str, known_ids: set):
    """Multi-chain query structures get indexed by Foldseek as one
    query per chain ("dam_A", "dam_B", ...). Collapse back to the
    single protein ID - but some protein IDs themselves contain
    underscores (e.g. "dcmp_hm"), so only strip a trailing
    "_<suffix>" segment if the remainder is itself a known query id
    (same approach already used for the reverse case - target-side
    chain suffixes - in backend/app/tasks.py::_base_protein_name)."""
    if query in known_ids:
        return query, None
    if "_" in query:
        prefix, suffix = query.rsplit("_", 1)
        if prefix in known_ids:
            return prefix, suffix
    return query, None


def apply_transform(coord: np.ndarray, u: np.ndarray, t: np.ndarray) -> np.ndarray:
    """new = U @ coord + t, per Foldseek's documented U/T convention
    (https://github.com/steineggerlab/foldseek/wiki - "How to apply U
    and T to a PDB file"): U is row-major (u[0:3] is the first row)."""
    return u.dot(coord) + t


def parse_ut(u_str: str, t_str: str):
    u = np.array([float(x) for x in u_str.split(",")], dtype=float).reshape(3, 3)
    t = np.array([float(x) for x in t_str.split(",")], dtype=float)
    return u, t


def build_pair_structure(query_chain, target_structure, u: np.ndarray, t: np.ndarray):
    """query_chain: a Bio.PDB Chain (unmodified). target_structure: the
    full Structure parsed from the target's CIF - transformed on a
    copy and relabelled to chain "B" (or the next free letter if "B"
    collides with the query chain's own id)."""
    new_structure = Structure.Structure("aligned_pair")
    new_model = Model.Model(0)
    new_structure.add(new_model)

    new_model.add(query_chain.copy())

    target_chain_id = "B" if query_chain.id != "B" else "C"
    combined_target_chain = Chain.Chain(target_chain_id)
    atom_serial = 1
    for chain in target_structure[0]:
        for residue in chain:
            new_residue = residue.copy()
            for atom in new_residue:
                atom.coord = apply_transform(np.array(atom.coord, dtype=float), u, t)
                atom.set_serial_number(atom_serial)
                atom_serial += 1
            try:
                combined_target_chain.add(new_residue)
            except Exception:
                pass  # duplicate residue id across what were multiple target chains - skip rather than crash
    new_model.add(combined_target_chain)
    return new_structure


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tsv", required=True, type=Path)
    parser.add_argument("--query-structures-dir", required=True, type=Path)
    parser.add_argument("--target-cif-dir", required=True, type=Path)
    parser.add_argument("--fallback-dir", type=Path, default=None,
                         help="Foldseek's own Calpha-only --format-mode 5 output, if you have it - "
                              "used only for hits whose target CIF wasn't fetchable. Optional; those "
                              "hits just get no structure if omitted (a small minority - see "
                              "fetch_euk_virus_target_structures.py's 'Unresolved' output).")
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    known_ids = {p.stem for p in args.query_structures_dir.iterdir() if p.is_file() and not p.name.startswith(".")}
    hits = read_hits(args.tsv)
    print(f"{len(hits)} hits to process")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    io = PDBIO()

    query_structure_cache: Dict[str, object] = {}
    target_structure_cache: Dict[str, object] = {}

    built, fell_back, skipped, errors = 0, 0, 0, []

    for i, hit in enumerate(hits):
        raw_query = hit["query"]
        target = hit["target"][:-4] if hit["target"].endswith(".pdb") else hit["target"]
        base_query, chain_letter = base_query_and_chain(raw_query, known_ids)

        out_dir = args.out_dir / raw_query
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{target}.pdb"
        if out_path.exists():
            continue

        target_cif = args.target_cif_dir / f"{target}.cif"
        if not target_cif.exists():
            if args.fallback_dir and args.fallback_dir.exists():
                fallback_matches = [
                    p for p in args.fallback_dir.iterdir()
                    if p.is_file() and raw_query in p.name and target in p.name
                ]
                if fallback_matches:
                    shutil.copyfile(fallback_matches[0], out_path)
                    fell_back += 1
                    continue
            skipped += 1
            continue

        try:
            if base_query not in query_structure_cache:
                qfile = find_query_file(args.query_structures_dir, base_query)
                if qfile is None:
                    raise FileNotFoundError(f"no query structure file for {base_query}")
                query_structure_cache[base_query] = load_structure(qfile)
            query_structure = query_structure_cache[base_query]

            if chain_letter and chain_letter in [c.id for c in query_structure[0]]:
                query_chain = query_structure[0][chain_letter]
            else:
                query_chain = next(iter(query_structure[0]))

            if target not in target_structure_cache:
                target_structure_cache[target] = load_structure(target_cif)
            target_structure = target_structure_cache[target]

            u, t = parse_ut(hit["u"], hit["t"])
            combined = build_pair_structure(query_chain, target_structure, u, t)
            io.set_structure(combined)
            io.save(str(out_path))
            built += 1
        except Exception as e:
            errors.append((raw_query, target, str(e)))

        if (i + 1) % 50 == 0:
            print(f"  ... {i + 1}/{len(hits)} processed")

    print(f"\nDone. Built (full-atom, two-chain): {built}  Fell back to Calpha-only: {fell_back}  "
          f"Skipped (no target structure available at all): {skipped}  Errors: {len(errors)}")
    if errors:
        print("\nErrors:", file=sys.stderr)
        for q, t, err in errors:
            print(f"  {q} vs {t}: {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
