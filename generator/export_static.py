#!/usr/bin/env python3
"""
Render the Django "explorer" app (vendored from anti_defence-main.zip) into
a static HTML tree, served from evades-webapp at /explore/.

This is a one-time/occasional generation step, not part of the running
app — see generator/README.md. Re-run whenever EVADES.json or the pipeline
outputs change.

Usage (from generator/):
    ./.venv/bin/python export_static.py
"""
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

GENERATOR_DIR = Path(__file__).resolve().parent
WEBSITE_DIR = GENERATOR_DIR / "website" / "anti_defence"
REPO_ROOT = GENERATOR_DIR.parent
OUT_DIR = REPO_ROOT / "frontend" / "explore"
# Where this app is mounted, e.g. "/explore/" self-hosted, or
# "/finn-srv/evades/explore/" nested under an EBI-style path prefix
# later — change only this one value to move it. Must end in
# "explore/"; SITE_ROOT (the parent app's root, used for the "back to
# main site" link) is derived from it below.
SCRIPT_PREFIX = "/explore/"
SITE_ROOT = SCRIPT_PREFIX.removesuffix("explore/")

os.environ["DATABASE_URL"] = f"sqlite:///{WEBSITE_DIR / 'anti_defence.sqlite3'}"
os.environ["DEBUG"] = "False"
os.environ["DJANGO_SECRET_KEY"] = "static-export-only"
os.environ["ALLOWED_HOST"] = "localhost"
os.environ["BASE_URL"] = f"http://localhost{SCRIPT_PREFIX.rstrip('/')}"
os.environ["SITE_ROOT"] = SITE_ROOT
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "anti_defence.settings")

sys.path.insert(0, str(WEBSITE_DIR))

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402
from django.urls import set_script_prefix  # noqa: E402
from explorer.models import Protein, ProteinDefences, ProteinPfams  # noqa: E402

set_script_prefix(SCRIPT_PREFIX)


def save(url_path: str, content: bytes) -> None:
    assert url_path.startswith("/") and url_path.endswith("/")
    target_dir = OUT_DIR / url_path.strip("/")
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "index.html").write_bytes(content)


def build_download_zip(protein: Protein) -> None:
    """One "download everything about this protein" bundle per detail
    page: sequence, structure file, secondary-structure JSON, homolog
    HTML (whichever of those exist), plus a metadata.json summary —
    the same data the detail page shows, machine-readable in one
    place instead of scattered across separate download buttons."""
    target_dir = OUT_DIR / "details" / protein.id
    target_dir.mkdir(parents=True, exist_ok=True)

    defences = [
        {"name": d.defence_name, "link": d.defence_link}
        for d in ProteinDefences.objects.filter(protein=protein)
    ]
    pfams = [
        {
            "name": p.pfam_name,
            "accession": p.pfam_accession,
            "length": p.pfam_length,
            "evalue": p.e_value,
            "hmm_from": p.hmm_from,
            "hmm_to": p.hmm_to,
            "ali_from": p.ali_from,
            "ali_to": p.ali_to,
            "env_from": p.env_from,
            "env_to": p.env_to,
        }
        for p in ProteinPfams.objects.filter(protein=protein)
    ]
    metadata = {
        "id": protein.id,
        "name": protein.name,
        "moa": protein.moa,
        "moa_category": protein.moa_category,
        "evidence": protein.evidence,
        "defence_subtype": protein.defence_subtype,
        "doi": protein.doi,
        "multicomponent": protein.multicomponent,
        "pdb": protein.pdb,
        "structure_type": protein.structure_type,
        "protein_source_name": protein.protein_source_name,
        "protein_source_link": protein.protein_source_link,
        "defences": defences,
        "pfam_annotations": pfams,
    }

    with zipfile.ZipFile(target_dir / "download.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadata.json", json.dumps(metadata, indent=2))
        if protein.sequence:
            zf.writestr(f"{protein.id}.fasta", f">{protein.id}\n{protein.sequence}\n")
        if protein.pdb_blob:
            ext = Path(protein.pdb_filename or "structure.pdb").suffix or ".pdb"
            zf.writestr(f"{protein.id}{ext}", protein.pdb_blob)
        if protein.pred_secondary_structure_blob:
            zf.writestr(
                f"{protein.id}_secondary_structure.json",
                protein.pred_secondary_structure_blob,
            )
        if protein.euk_virus_homologs_blob:
            zf.writestr(f"{protein.id}_homologs.html", protein.euk_virus_homologs_blob)


def fetch(client: Client, url_path: str) -> bool:
    response = client.get(url_path, SERVER_NAME="localhost")
    if response.status_code != 200:
        print(f"  WARN {url_path} -> HTTP {response.status_code}")
        return False
    save(url_path, response.content)
    return True


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    client = Client()

    print("Rendering index + protein_list ...")
    fetch(client, "/")
    fetch(client, "/protein_list/")

    proteins = list(Protein.objects.all())
    print(f"Rendering {len(proteins)} protein detail pages + blobs ...")
    ok = 0
    for p in proteins:
        pid = p.id
        if fetch(client, f"/details/{pid}/"):
            ok += 1
        if p.pdb_blob is not None:
            fetch(client, f"/serve_blob/{pid}/pdb_blob/")
        if p.pred_secondary_structure_blob is not None:
            fetch(client, f"/serve_blob/{pid}/pred_secondary_structure_blob/")
        if p.euk_virus_homologs_blob is not None:
            fetch(client, f"/euk_virus_homologs/{pid}/")
        build_download_zip(p)
    print(f"Detail pages rendered: {ok}/{len(proteins)}")

    static_src = WEBSITE_DIR / "explorer" / "static" / "explorer"
    static_dst = OUT_DIR / "static" / "explorer"
    static_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
    print(f"Copied static assets -> {static_dst}")

    print(f"\nDone. Static site written to {OUT_DIR}")


if __name__ == "__main__":
    main()
