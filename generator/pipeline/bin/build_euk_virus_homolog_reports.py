#!/usr/bin/env python3
"""
Build a sortable/searchable/downloadable homolog report per query
protein, from the outputs of fetch_euk_virus_target_structures.py and
build_euk_virus_aligned_structures.py — replacing the externally-
computed, closed HTML reports this directory used to hold (Foldseek's
own self-contained --format-mode 3/4 HTML, whose minified bundle
turned out too fragile to safely make sortable in place: it reuses one
shared, un-id'd DOM node for whichever result is currently toggled
open, found via an unguarded querySelector - moving or removing
anything in that table broke "Toggle" page-wide, not just for the row
touched). This generates the same thing ourselves, as plain code we
control, with real per-hit structural alignments as a bonus (the
reviewer's second complaint - only a static PNG was downloadable
before).

Writes directly into assets/homologs/<query>.html — the exact path
update_euk_virus_homolog_blobs.py already reads from, so nothing else
in the pipeline needs to change. Its DataTables patch
(make_table_sortable()) automatically no-ops on these reports (it only
triggers on Foldseek's own "tableBody"-id'd markup, which these don't
have — they're already sortable on their own).

Only touches assets/homologs/<query>.html for proteins that got at
least one hit in this run — a protein with no hits this time keeps
whatever homolog report (if any) it already had, rather than losing
real existing data to an empty result.

Structure data is embedded directly in each page (loaded into the 3D
viewer via an in-memory Blob, "Download" triggered the same way) -
not fetched from a separate file at click-time, so these work when
opened straight from disk, not just when served by nginx.

Usage (from generator/):
    ./.venv/bin/python pipeline/bin/build_euk_virus_homolog_reports.py \\
        --tsv assets/euk_virus_homolog_search/results.tsv \\
        --aligned-structures-dir work/euk_virus_aligned_structures \\
        --query-structures-dir assets/structures/EVADES_v1 \\
        --out-dir assets/homologs
"""
import argparse
import csv
import html
import json
import sys
from pathlib import Path
from typing import Dict, List

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
                print(f"  WARN skipping malformed row (expected {len(COLUMNS)} columns, got {len(row)}): {row[:2]}", file=sys.stderr)
                continue
            hits.append(dict(zip(COLUMNS, row)))
    return hits


def load_known_query_ids(query_structures_dir: Path) -> set:
    return {p.stem for p in query_structures_dir.iterdir() if p.is_file() and not p.name.startswith(".")}


def base_query_name(query: str, known_ids: set) -> str:
    """Same collapsing rule as build_euk_virus_aligned_structures.py's
    base_query_and_chain() - multi-chain queries ("dam_A", "dam_B", ...)
    collapse back to one report per protein ("dam"), careful not to
    mis-split IDs that already contain underscores (e.g. "dcmp_hm")."""
    if query in known_ids:
        return query
    if "_" in query:
        prefix = query.rsplit("_", 1)[0]
        if prefix in known_ids:
            return prefix
    return query


def render_query_report(query: str, hits: List[Dict], aligned_structures_dir: Path) -> str:
    rows = []
    missing = 0
    for hit in hits:
        target = hit["target"][:-4] if hit["target"].endswith(".pdb") else hit["target"]
        src = aligned_structures_dir / hit["query"] / f"{target}.pdb"
        pdb_text = None
        if src.exists():
            pdb_text = src.read_text(errors="replace")
        else:
            missing += 1
        rows.append({
            "target": hit["target"],
            "fident": round(float(hit["fident"]), 3),
            "alntmscore": round(min(float(hit["alntmscore"]), 1.0), 3),
            "prob": round(float(hit["prob"]), 3),
            "alnlen": int(hit["alnlen"]),
            "query_pos": f"{hit['qstart']}-{hit['qend']}",
            "target_pos": f"{hit['tstart']}-{hit['tend']}",
            "lddt": round(float(hit["lddt"]), 3),
            "structure_pdb": pdb_text,
        })
    if missing:
        print(f"  WARN {query}: no aligned structure found for {missing}/{len(hits)} hits - "
              f"run build_euk_virus_aligned_structures.py first if you haven't", file=sys.stderr)

    rows.sort(key=lambda r: -r["alntmscore"])
    return _TEMPLATE.format(
        query=html.escape(query),
        n_hits=len(rows),
        data_json=json.dumps(rows),
    )


_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{query} - eukaryotic virus homologs</title>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.8/css/jquery.dataTables.min.css">
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 2rem; }}
  #viewer {{ width: 100%; height: 420px; border: 1px solid #ccc; margin-bottom: 1rem; }}
  #viewer-caption {{ font-size: 0.9em; color: #555; margin-bottom: 0.5rem; }}
  table.dataTable {{ font-size: 0.9em; }}
  a.view-link, a.download-link {{ cursor: pointer; }}
</style>
</head>
<body>
<h1>{query} &mdash; eukaryotic dsDNA virus homologs</h1>
<p>{n_hits} hits (TM-score &ge; the filter used at search time). Click "View" to load a hit's
aligned structure below - chain A (blue) is {query} unmodified, chain B (red) is the target
superposed onto it using Foldseek's own alignment transform, applied to the target's real
full-atom predicted structure where one was available (falls back to Foldseek's own
Calpha-only structure, target chain only, otherwise - single chain in that case).
"Download" gets the same structure as a .pdb file.</p>

<div id="viewer-caption">No structure loaded - click "View" on any row.</div>
<div id="viewer"></div>

<table id="hits" class="display">
<thead><tr>
  <th>Target</th><th>Seq. Identity</th><th>TM-score</th><th>Prob.</th>
  <th>Aln. Length</th><th>Query Pos.</th><th>Target Pos.</th><th>LDDT</th><th></th>
</tr></thead>
<tbody></tbody>
</table>

<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js"></script>
<script src="https://cdn.datatables.net/1.13.8/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/ngl@2.4.0/dist/ngl.js"></script>
<script>
var ROWS = {data_json};
var stage = null;

function loadStructure(pdbText, label) {{
    if (!pdbText) {{
        document.getElementById("viewer-caption").textContent =
            "No structure for " + label + ".";
        return;
    }}
    if (!stage) stage = new NGL.Stage("viewer");
    stage.removeAllComponents();
    document.getElementById("viewer-caption").textContent = "Loading " + label + " ...";
    // Loaded from a Blob built from data embedded in this page, not a
    // fetch() of a separate file - works even opened straight from
    // disk (file://), where browsers block fetch() against local files.
    var blob = new Blob([pdbText], {{ type: "text/plain" }});
    stage.loadFile(blob, {{ ext: "pdb" }}).then(function (comp) {{
        var chainNames = {{}};
        comp.structure.eachChain(function (c) {{ chainNames[c.chainname] = true; }});
        var chainCount = Object.keys(chainNames).length;
        comp.addRepresentation("cartoon", {{ color: "chainid" }});
        stage.autoView();
        document.getElementById("viewer-caption").textContent = (chainCount > 1)
            ? (label + " - chain A = query, chain B = target, full atom")
            : (label + " - Calpha-only target only (no full-atom structure was available for this hit; query not shown)");
    }}).catch(function (err) {{
        document.getElementById("viewer-caption").textContent =
            "Failed to render " + label + ": " + err.message;
    }});
}}

function downloadStructure(pdbText, filename) {{
    var blob = new Blob([pdbText], {{ type: "text/plain" }});
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}}

$(document).ready(function () {{
    var table = $("#hits").DataTable({{
        pageLength: 25,
        order: [[2, "desc"]],
        data: ROWS,
        columns: [
            {{ data: "target" }},
            {{ data: "fident" }},
            {{ data: "alntmscore" }},
            {{ data: "prob" }},
            {{ data: "alnlen" }},
            {{ data: "query_pos" }},
            {{ data: "target_pos" }},
            {{ data: "lddt" }},
            {{
                data: null,
                orderable: false,
                render: function (row) {{
                    if (!row.structure_pdb) return "(no structure)";
                    return '<a class="view-link">View</a> | <a class="download-link">Download</a>';
                }}
            }}
        ]
    }});

    $("#hits tbody").on("click", "a.view-link", function () {{
        var row = table.row($(this).closest("tr")).data();
        loadStructure(row.structure_pdb, row.target);
    }});
    $("#hits tbody").on("click", "a.download-link", function () {{
        var row = table.row($(this).closest("tr")).data();
        downloadStructure(row.structure_pdb, row.target + ".pdb");
    }});
}});
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tsv", required=True, type=Path)
    parser.add_argument("--aligned-structures-dir", required=True, type=Path)
    parser.add_argument("--query-structures-dir", required=True, type=Path,
                         help="assets/structures/EVADES_v1 - used to know the canonical protein IDs "
                              "(for collapsing multi-chain queries like dam_A, dam_B, ... back to one report per protein)")
    parser.add_argument("--out-dir", required=True, type=Path, help="assets/homologs - written in place")
    args = parser.parse_args()

    known_ids = load_known_query_ids(args.query_structures_dir)
    hits = read_hits(args.tsv)
    print(f"Read {len(hits)} hits for {len(set(h['query'] for h in hits))} raw queries from {args.tsv}")

    by_query: Dict[str, List[Dict]] = {}
    for hit in hits:
        base = base_query_name(hit["query"], known_ids)
        by_query.setdefault(base, []).append(hit)

    # Multi-chain proteins can have the same target hit independently
    # via more than one chain - keep only the best (highest TM-score)
    # row per (protein, target) so it doesn't appear twice in one report.
    for base, base_hits in by_query.items():
        best_per_target: Dict[str, Dict] = {}
        for hit in base_hits:
            existing = best_per_target.get(hit["target"])
            if existing is None or float(hit["alntmscore"]) > float(existing["alntmscore"]):
                best_per_target[hit["target"]] = hit
        by_query[base] = list(best_per_target.values())

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for query, query_hits in sorted(by_query.items()):
        report_html = render_query_report(query, query_hits, args.aligned_structures_dir)
        out_path = args.out_dir / f"{query}.html"
        out_path.write_text(report_html)
        print(f"  wrote {out_path} ({len(query_hits)} hits)")

    zero_hit = sorted(known_ids - set(by_query.keys()))
    if zero_hit:
        print(f"\n{len(zero_hit)} proteins had NO hits in this run - their assets/homologs/<id>.html "
              f"(if any) was left untouched rather than overwritten with nothing: " + ", ".join(zero_hit))

    print(f"\nDone.")


if __name__ == "__main__":
    main()
