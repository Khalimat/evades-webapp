# Explore-tab generator

The "Explore" tab (`/explore/...`) is a **static** rendering of the EVADES
protein browser — the same page as
https://www.ebi.ac.uk/finn-srv/evades/protein_list/, generated from the
Django app + Nextflow pipeline in `anti_defence-main.zip`.

It is **not** a running service. Nothing here ships in a Docker image or
runs at request time — `export_static.py` renders every page once into
`frontend/explore/`, which nginx then serves as plain files (see the
`/explore/` block in `nginx/default.conf`). This keeps the deployed stack
exactly what it was before (nginx + FastAPI `api`/`worker` + Postgres +
Redis for the Analyse tab) with no new always-on service, no extra
Postgres tables, no Django/gunicorn in production.

Re-run this whenever `EVADES.json` (the curated protein metadata) changes.
Everything under `generator/` except this README, `export_static.py`,
`generate.sh` and the vendored `pipeline/`/`website/` code is gitignored —
it's either a one-time tool download or heavy input data, not source.

## One-time setup

```bash
cd generator

# Nextflow's portable launcher needs a JVM. This installs OpenJDK via
# Homebrew (reversible: `brew uninstall openjdk`) and a self-contained
# nextflow binary in generator/tools/ (not on your system PATH).
brew install openjdk
JAVA_HOME="/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home" \
  PATH="/opt/homebrew/opt/openjdk/bin:$PATH" \
  bash -c 'mkdir -p tools && cd tools && curl -s https://get.nextflow.io | bash'
# (generate.sh below doesn't actually invoke nextflow — see "Why a
# shell script and not `nextflow run`?" — but it's there if you want it.)

python3 -m venv .venv
./.venv/bin/pip install django==4.2.3 django-environ==0.12.0
# Note: biopython was in the original website/requirements.txt but is
# never imported anywhere in the vendored code — dropped.
```

## Assets you need in `generator/assets/`

| Path                               | What                                                              | Source |
|-------------------------------------|--------------------------------------------------------------------|--------|
| `assets/Pfam-A.hmm.gz`             | Full Pfam-A HMM database                                          | ftp.ebi.ac.uk/pub/databases/Pfam |
| `assets/homologs/`                 | `<id>.html` pages, eukaryotic-dsDNA-virus homolog hits per protein | computed externally, curator-provided |
| `assets/structures/EVADES_v1/`     | `.pdb`/`.cif` files (extract `data/downloads/predicted_structures.tar.gz`) | already in this repo's `data/downloads/` |
| `pipeline/assets/EVADES.json`      | Curated protein metadata (268 proteins)                           | curator-provided |

`generate.sh` checks these exist before doing anything.

## Regenerating

```bash
cd generator
./generate.sh
```

This runs the same steps as `pipeline/main.nf`, in the same order, against
a fresh SQLite DB at `website/anti_defence/anti_defence.sqlite3`:

1. `manage.py migrate` — create the schema
2. `extract_fasta.py` — pull all sequences out of `EVADES.json`
3. `hmmsearch --cut_tc` against `Pfam-A.hmm` (via the `quay.io/biocontainers/hmmer` image — no local HMMER install needed) → `parse_domtbl.py`
4. S4PRED secondary-structure prediction (via `quay.io/biocontainers/s4pred`) → `parse_s4pred_to_feature_viewer.py`
5. `update_proteins.py`, `update_pdb_blobs.py`, `update_euk_virus_homolog_blobs.py`, `update_protein_pfams.py`, `update_secondary_structure_blobs.py` — load everything into the DB
6. `export_static.py` — walk every page + blob URL via Django's test client and write it to `frontend/explore/<path>/index.html`, plus copy the app's static assets (css/js/icons)

Takes ~15-20 minutes, mostly S4PRED (CPU-only, and emulated if you're on
Apple Silicon since the biocontainer is linux/amd64 only).

### Why a shell script and not `nextflow run pipeline`?

The original repo's `main.nf` is the "real"/reproducible way to run this
on a cluster, and `generator/tools/nextflow` is installed and ready if you
want it (`nextflow run pipeline -profile docker`, after fixing the DB/asset
paths — see the original `anti_defence-main` README, also unpacked
alongside this one for reference). For a one-off local generation,
`generate.sh` runs the exact same commands directly, which is easier to
debug when something's missing and avoids relying on Nextflow's local
process staging matching up with Django's `DATABASE_URL` env var — this
does work, but a plain script is more transparent for infrequent, manual
re-runs.

### Two bugs fixed vs. upstream `anti_defence-main`

- `modules/local/update_protein_pfams/main.nf` called
  `update_protein_pfams.py --domtbl ...` but the script's argparse only
  defines `--domtbl_csv` — would fail outright under `nextflow run`. Fixed
  the module to pass the right flag.
- `update_euk_virus_homolog_blobs.py` looked up homolog files by the exact
  filename in `EVADES.json` (e.g. `pnk_model.html`), but the actual
  homolog folder has `pnk.html` (no `_model` suffix) for all 27 proteins
  that have homolog data. Fixed by normalizing the filename before the
  lookup.

## Wiring

- `nginx/default.conf` — `location /explore/ { try_files $uri $uri/index.html =404; }`, under the existing `root /usr/share/nginx/html;` (the `frontend/` bind mount), so `frontend/explore/` is served automatically once it exists — no image rebuild.
- `frontend/index.html` — the "Explore" tab now links to `/explore/protein_list/` instead of the external `https://www.ebi.ac.uk/finn-srv/evades/protein_list/`.
- The Analyse tab (FastAPI `api`/`worker`, HMM + Foldseek search on user-uploaded FASTA) is untouched — completely separate code path, separate Postgres DB (`evades`), separate containers.
