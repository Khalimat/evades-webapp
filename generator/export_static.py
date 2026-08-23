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
import os
import shutil
import sys
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
from explorer.models import Protein  # noqa: E402

set_script_prefix(SCRIPT_PREFIX)


def save(url_path: str, content: bytes) -> None:
    assert url_path.startswith("/") and url_path.endswith("/")
    target_dir = OUT_DIR / url_path.strip("/")
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "index.html").write_bytes(content)


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

    proteins = list(
        Protein.objects.all().values(
            "id", "pdb_blob", "pred_secondary_structure_blob", "euk_virus_homologs_blob"
        )
    )
    print(f"Rendering {len(proteins)} protein detail pages + blobs ...")
    ok = 0
    for p in proteins:
        pid = p["id"]
        if fetch(client, f"/details/{pid}/"):
            ok += 1
        if p["pdb_blob"] is not None:
            fetch(client, f"/serve_blob/{pid}/pdb_blob/")
        if p["pred_secondary_structure_blob"] is not None:
            fetch(client, f"/serve_blob/{pid}/pred_secondary_structure_blob/")
        if p["euk_virus_homologs_blob"] is not None:
            fetch(client, f"/euk_virus_homologs/{pid}/")
    print(f"Detail pages rendered: {ok}/{len(proteins)}")

    static_src = WEBSITE_DIR / "explorer" / "static" / "explorer"
    static_dst = OUT_DIR / "static" / "explorer"
    static_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
    print(f"Copied static assets -> {static_dst}")

    print(f"\nDone. Static site written to {OUT_DIR}")


if __name__ == "__main__":
    main()
