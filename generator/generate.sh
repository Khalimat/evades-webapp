#!/usr/bin/env bash
# Regenerate the static /explore/ site from generator/pipeline/assets/EVADES.json
# and the assets in generator/assets/. See generator/README.md for what
# needs to exist in generator/assets/ before running this, and for how
# this maps onto the original anti_defence-main pipeline/main.nf.
#
# Usage: ./generate.sh   (run from the generator/ directory)
set -euo pipefail

cd "$(dirname "$0")"

PY=./.venv/bin/python
DB=website/anti_defence/anti_defence.sqlite3
ASSETS=assets

if [ ! -x "$PY" ]; then
    echo "Missing generator/.venv — run: python3 -m venv .venv && ./.venv/bin/pip install django==4.2.3 django-environ==0.12.0" >&2
    exit 1
fi
for needed in "$ASSETS/Pfam-A.hmm.gz" "$ASSETS/homologs" "$ASSETS/structures" pipeline/assets/EVADES.json; do
    if [ ! -e "$needed" ]; then
        echo "Missing $needed — see generator/README.md for what to put in generator/assets/." >&2
        exit 1
    fi
done

export DATABASE_URL="sqlite:///$(pwd)/$DB"
export DEBUG=True
export DJANGO_SECRET_KEY="local-generation-only"
export ALLOWED_HOST="localhost"

echo "==> Fresh DB schema"
rm -f "$DB"
(cd website/anti_defence && ../../"$PY" manage.py migrate)

echo "==> Decompressing Pfam-A.hmm (if needed)"
[ -f "$ASSETS/Pfam-A.hmm" ] || gunzip -k "$ASSETS/Pfam-A.hmm.gz"

echo "==> Extracting FASTA of all protein sequences"
$PY pipeline/bin/extract_fasta.py \
    --input_file pipeline/assets/EVADES.json \
    --output_fasta "$ASSETS/proteins.fasta"

echo "==> hmmsearch against Pfam-A (via biocontainer, ~5 min)"
mkdir -p "$ASSETS/hmmsearch_out"
docker run --rm -v "$(pwd)/$ASSETS":/data \
    quay.io/biocontainers/hmmer:3.4--hdbdd923_1 \
    hmmsearch --cut_tc --cpu 4 \
        -o /data/hmmsearch_out/anti-defence.txt \
        --domtblout /data/hmmsearch_out/anti-defence.domtbl \
        /data/Pfam-A.hmm /data/proteins.fasta
$PY pipeline/bin/parse_domtbl.py \
    --domtbl "$ASSETS/hmmsearch_out/anti-defence.domtbl" \
    --out_csv "$ASSETS/hmmsearch_out/protein_pfams.csv"

echo "==> S4PRED secondary structure prediction (via biocontainer, ~10 min on CPU)"
mkdir -p "$ASSETS/s4pred_out"
docker run --rm -v "$(pwd)/$ASSETS":/data \
    quay.io/biocontainers/s4pred:1.2.1--pyhdfd78af_1 \
    run_model --outfmt horiz --threads 4 --save-files \
        --outdir /data/s4pred_out /data/proteins.fasta
$PY pipeline/bin/parse_s4pred_to_feature_viewer.py \
    "$ASSETS/s4pred_out" "$ASSETS/s4pred_features"

echo "==> Eukaryotic-virus homolog structural search (optional - only if $ASSETS/euk_virus_homolog_search/results.tsv exists)"
if [ -f "$ASSETS/euk_virus_homolog_search/results.tsv" ]; then
    RESULTS_TSV="$ASSETS/euk_virus_homolog_search/results.tsv"
    $PY pipeline/bin/fetch_euk_virus_target_structures.py \
        --tsv "$RESULTS_TSV" \
        --out-dir work/euk_virus_target_structures_cif
    $PY pipeline/bin/build_euk_virus_aligned_structures.py \
        --tsv "$RESULTS_TSV" \
        --query-structures-dir "$ASSETS/structures/EVADES_v1" \
        --target-cif-dir work/euk_virus_target_structures_cif \
        --out-dir work/euk_virus_aligned_structures
    $PY pipeline/bin/build_euk_virus_homolog_reports.py \
        --tsv "$RESULTS_TSV" \
        --aligned-structures-dir work/euk_virus_aligned_structures \
        --query-structures-dir "$ASSETS/structures/EVADES_v1" \
        --out-dir "$ASSETS/homologs"
else
    echo "  (skipped - no $ASSETS/euk_virus_homolog_search/results.tsv; using $ASSETS/homologs/ as-is)"
fi

echo "==> Loading everything into the DB"
(cd website/anti_defence && \
    ../../"$PY" ../../pipeline/bin/update_proteins.py \
        --input_json ../../pipeline/assets/EVADES.json && \
    ../../"$PY" ../../pipeline/bin/update_pdb_blobs.py \
        --db "$(basename "$DB")" --structures ../../"$ASSETS"/structures/EVADES_v1 && \
    ../../"$PY" ../../pipeline/bin/update_euk_virus_homolog_blobs.py \
        --db "$(basename "$DB")" --homologs ../../"$ASSETS"/homologs && \
    ../../"$PY" ../../pipeline/bin/update_protein_pfams.py \
        --domtbl_csv ../../"$ASSETS"/hmmsearch_out/protein_pfams.csv --db "$(basename "$DB")" && \
    ../../"$PY" ../../pipeline/bin/update_secondary_structure_blobs.py \
        ../../"$ASSETS"/s4pred_features "$(basename "$DB")")

echo "==> Rendering static site to frontend/explore/"
$PY export_static.py

echo "==> Done."
