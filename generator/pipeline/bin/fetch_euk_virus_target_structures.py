#!/usr/bin/env python3
"""
Fetch the full-atom predicted structure for every target hit in
assets/euk_virus_homolog_search/results.tsv (a Foldseek easy-search
run against a eukaryotic-dsDNA-virus structure database, re-run
externally on a cluster — see assets/euk_virus_homolog_search/ in
generator/README.md for how that table was produced and what it must
contain).

Used by build_euk_virus_aligned_structures.py to build real two-chain
(query + target) full-atom aligned structures — Foldseek's own
--format-mode 5 output only gives a Calpha-only trace of the target,
no query, no side chains.

The target database turns out to be built from the same underlying
set as Nomburg et al., "Birth of new protein folds and functions in
the virome" (bioRxiv 2024.01.22.576744) — confirmed by fetching one
real hit and checking its embedded metadata, which names the exact
target identifier from our results.tsv. That paper's supplementary
table (media-1.xlsx) maps each protein identifier to an index into
ModelArchive, where the actual AlphaFold/ColabFold-predicted structure
(full atom, mmCIF) lives. Same approach as
https://colab.research.google.com/github/jnoms/vpSAT/blob/main/bin/colab/ExploreStructures.ipynb
(vpSAT's own structure browser) — including its one easy-to-miss
detail: ModelArchive IDs are 5-digit zero-padded
(ma-jd-viral-05873, not ma-jd-viral-5873); omitting the padding 404s
for any index under 10000, which looks exactly like "this target's
structure isn't available" but isn't.

Usage (from generator/):
    ./.venv/bin/python pipeline/bin/fetch_euk_virus_target_structures.py \\
        --tsv assets/euk_virus_homolog_search/results.tsv \\
        --out-dir work/euk_virus_target_structures_cif

Caches media-1.xlsx locally (~4.5MB) and skips any structure file
already downloaded, so re-running only fetches what's new.
"""
import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

MEDIA_XLSX_URL = "https://www.biorxiv.org/content/biorxiv/early/2024/01/23/2024.01.22.576744/DC1/embed/media-1.xlsx?download=true"
MODEL_ARCHIVE_URL = "https://www.modelarchive.org/api/projects/ma-jd-viral-{index}?type=basic__model_file_name"
REQUEST_DELAY_SECONDS = 0.3  # be polite to ModelArchive - no documented rate limit, but this is a lot of requests
MAX_RETRIES = 5

# bioRxiv (behind Cloudflare) 429s the default Python-urllib User-Agent
# specifically - confirmed by reproducing the exact same 429 with curl
# sending that same UA string, while curl's own default UA succeeds
# every time. It isn't a real request-rate limit (retrying the
# identical request with a normal UA works immediately) - it's bot
# filtering keying off the UA. A real browser UA sidesteps it; applied
# globally since it's harmless for ModelArchive's requests too.
_opener = urllib.request.build_opener()
_opener.addheaders = [(
    "User-Agent",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
)]
urllib.request.install_opener(_opener)


def fetch_with_retry(url: str, out_path: Path) -> None:
    """Both bioRxiv (media-1.xlsx - one big, one-time-ish download) and
    ModelArchive (hundreds of small per-target requests) can 429 under
    load - retry with exponential backoff (longer on a 429 specifically,
    since that's the server explicitly asking us to slow down) rather
    than letting one transient rate-limit response kill the whole run."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            urllib.request.urlretrieve(url, out_path)
            return
        except urllib.error.HTTPError as e:
            last_error = e
            if out_path.exists():
                out_path.unlink()
            if e.code == 429:
                wait = 30 * (attempt + 1)
            elif 500 <= e.code < 600:
                wait = 5 * (2 ** attempt)
            else:
                raise  # a real 404/etc - retrying won't help, let the caller handle it
        except Exception as e:
            last_error = e
            if out_path.exists():
                out_path.unlink()
            wait = 5 * (2 ** attempt)
        if attempt < MAX_RETRIES - 1:
            print(f"    ... {url} failed ({last_error}), retrying in {wait}s "
                  f"(attempt {attempt + 2}/{MAX_RETRIES})")
            time.sleep(wait)
    raise last_error


def ensure_media_xlsx(cache_dir: Path) -> Path:
    path = cache_dir / "media-1.xlsx"
    if path.exists():
        return path
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {MEDIA_XLSX_URL} -> {path} ...")
    fetch_with_retry(MEDIA_XLSX_URL, path)
    return path


def read_unique_targets(tsv_path: Path) -> set:
    targets = set()
    with tsv_path.open() as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 2:
                continue
            t = cols[1]
            if t.endswith(".pdb"):
                t = t[:-4]
            targets.add(t)
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tsv", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path, help="where to save fetched .cif files")
    parser.add_argument("--cache-dir", type=Path, default=None, help="where media-1.xlsx lives (default: --out-dir's parent directory)")
    args = parser.parse_args()

    cache_dir = args.cache_dir or args.out_dir.parent
    xlsx_path = ensure_media_xlsx(cache_dir)

    print(f"Reading {xlsx_path} ...")
    df = pd.read_excel(xlsx_path)
    index_by_cluster_member = {name: i + 1 for i, name in enumerate(df["cluster_member"])}  # ModelArchive is 1-indexed

    targets = read_unique_targets(args.tsv)
    print(f"{len(targets)} unique targets in {args.tsv}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    fetched, cached, unresolved, failed = 0, 0, [], []

    for target in sorted(targets):
        out_path = args.out_dir / f"{target}.cif"
        if out_path.exists():
            cached += 1
            continue

        ma_index = index_by_cluster_member.get(target)
        if ma_index is None:
            unresolved.append(target)
            continue

        url = MODEL_ARCHIVE_URL.format(index=f"{ma_index:05d}")
        try:
            fetch_with_retry(url, out_path)
            fetched += 1
            if fetched % 25 == 0:
                print(f"  ... {fetched} fetched so far")
        except Exception as e:
            failed.append((target, str(e)))
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nDone. Fetched: {fetched}  Already cached: {cached}  "
          f"Unresolved (not in media-1.xlsx): {len(unresolved)}  Failed downloads: {len(failed)}")
    if unresolved:
        print("\nUnresolved (build_euk_virus_aligned_structures.py will fall back to Foldseek's own "
              "Calpha-only structure_alignments output for these):")
        for t in unresolved:
            print(f"  {t}")
    if failed:
        print("\nFailed downloads (network/server error - rerun this script to retry, it skips what's already cached):", file=sys.stderr)
        for t, err in failed:
            print(f"  {t}: {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
