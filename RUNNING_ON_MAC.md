# Running on a Mac — step by step

## 1. Install Docker Desktop

```bash
brew install --cask docker
open -a Docker
```

Wait for the whale icon in the menu bar to stop animating (Docker
engine fully started). Confirm:

```bash
docker version
docker info | grep Architecture
```

On Apple Silicon you should see `Architecture: aarch64`. That's
expected and good — it means containers build and run natively
(no Rosetta slowdown), including the Foldseek arm64 binary this
project's worker Dockerfile now selects automatically.

## 2. Get a minimal smoke-test dataset

Before wiring in your real 268 structures and full HMM library, prove
the pipeline works end-to-end with something tiny. From the project
root:

```bash
mkdir -p data/hmm data/foldseek data/downloads structures_tmp

# a) A single small HMM profile to search against (use any real Pfam
#    HMM you have handy, or press an empty placeholder just to test
#    plumbing — replace with your real EVADES profiles afterwards)
# Example using a Pfam HMM you already have locally:
#   cp /path/to/some_profile.hmm data/hmm/evades_profiles.hmm
#   hmmpress data/hmm/evades_profiles.hmm

# b) A tiny Foldseek DB from 2-3 structures you already have,
#    e.g. any PDB files sitting in your EVADES working folder
#    cp your_test_structures/*.pdb structures_tmp/
#    foldseek createdb structures_tmp/ data/foldseek/evades_structures_db
```

If you don't have files handy yet, just start the stack (step 3) —
the `/api/search/hmm` and `/api/search/structure` endpoints will
return a clear `RuntimeError` telling you the DB is missing, which at
least confirms the API → worker → error-reporting path works.

## 3. Build and start everything

```bash
cp .env.example .env   # if present; otherwise defaults in docker-compose.yml are fine
docker compose up --build
```

First build will take a few minutes (downloading base images, HMMER
via apt, the Foldseek binary). Watch for:

- `db` and `redis` becoming healthy
- `api` logging `Uvicorn running on http://0.0.0.0:8000`
- `worker` logging `Listening on default...` (RQ worker ready)
- `nginx` starting without config errors

## 4. Smoke-test each layer

**API is up:**
```bash
curl http://localhost:8080/api/health
# {"status":"ok"}
```

**Frontend loads:**
Open `http://localhost:8080` in a browser — you should see the
Download / Analyse tabs.

**A real HMM search (once you've dropped in a test HMM DB):**
```bash
curl -F "fasta=@/path/to/test_protein.fasta" http://localhost:8080/api/search/hmm
# {"id": "...", "status": "queued", "job_type": "hmm"}
```

Grab the returned `id` and poll:
```bash
curl http://localhost:8080/api/jobs/<id>
```
Watch `status` move from `queued` → `started` → `finished`, with
`result.hits` populated.

**Or just use the browser** — upload a FASTA on the Analyse tab and
watch the status text and results table update.

## 5. Common Mac-specific snags

- **"Cannot connect to Docker daemon"** — Docker Desktop isn't
  running yet; wait for the whale icon, or `open -a Docker` again.
- **Slow first build** — the worker image downloads HMMER via apt and
  compiles nothing (Foldseek is a static binary), so this should be a
  few minutes, not longer. If it hangs, check your network isn't
  blocking `mmseqs.com` or `deb.debian.org`.
- **Port 8080 already in use** — something else is bound to it;
  change the left-hand side of `"8080:80"` in `docker-compose.yml` to
  e.g. `"8090:80"` and use that port instead.
- **File upload limit errors** — if a structure or FASTA is large,
  bump `client_max_body_size` in `nginx/default.conf`.

## 6. Once it all works locally

- Replace the smoke-test HMM/Foldseek DBs with your real EVADES data.
- Tear down and rebuild clean to make sure nothing stale is cached:
  ```bash
  docker compose down -v
  docker compose up --build
  ```
- Then move on to deploying the same `docker-compose.yml` to a real
  VM (Hetzner/DigitalOcean now, Embassy Cloud later) — nothing in the
  compose file needs to change, just where it runs.
