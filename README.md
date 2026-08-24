# EVADES web app

Self-hosted companion site for the EVADES database: bulk downloads,
an "Explore" tab (the protein browser, statically generated — see
`generator/README.md`), and an "Analyse" tab (HMM search via HMMER,
structure search via Foldseek). No dependency on EBI infrastructure —
runs entirely in Docker Compose, portable to any VM (Hetzner,
DigitalOcean, or later EMBL-EBI's Embassy Cloud).

## Architecture

```
 browser
    |
  nginx  (reverse proxy, port 8080)
    |
    +--> static frontend (HTML/JS)
    +--> /explore/* --> statically-rendered protein browser (frontend/explore/)
    +--> /api/*  --> api (FastAPI)
    |                  |
    |               enqueues job
    |                  v
    |                redis (job queue)
    |                  ^
    |               picks up job
    |                  |
    +--> /downloads --> worker (FastAPI code + HMMER + Foldseek)
                           |
                        reads /data (HMM DB, Foldseek DB)
                           |
                        writes results to Postgres via api's DB
```

The `api` container never runs HMMER/Foldseek itself — it only
enqueues jobs onto a Redis queue (via [RQ](https://python-rq.org/)).
The `worker` container is the only place those tools run, and it's
the piece you scale for concurrency — see "Handling concurrent
requests" below.

## Quick start (local)

1. Build the databases — see `data/README.md`.
2. `cp .env.example .env` and adjust if needed (defaults work for local dev).
3. `docker compose up --build`
4. Visit `http://localhost:8080`

## Handling concurrent requests

The job queue (Redis + RQ) already decouples "someone hit Run search"
from "an HMMER/Foldseek process is actually running" — the `api`
container enqueues instantly regardless of load, so submissions never
block or fail under concurrency, they just queue up. Whether they
queue *and wait* or run *in parallel* depends only on how many
`worker` containers are up:

```bash
docker compose up -d --scale worker=3
```

No code or compose-file changes needed for this — verified locally by
submitting 3 searches at once with `--scale worker=3` and confirming
via `docker compose logs worker` that all three were picked up by
different worker containers at the same timestamp, not processed one
after another.

Each search job is capped at 2 threads (`hmmsearch --cpu 2`,
`foldseek --threads 2`), so worker replicas don't fight each other for
every core on the box. Size the VPS accordingly:

**vCPUs needed ≈ 2 × the number of searches you want to run genuinely
in parallel.** E.g. 4 vCPUs comfortably runs 2 worker replicas; 8
vCPUs runs 4. Anything beyond that just queues (a few seconds' wait,
not a failure) until a worker frees up.

This is the same mechanism that carries over to EBI's Kubernetes
later — `replicas: N` on the worker Deployment instead of `--scale`,
nothing else changes.

## What to fill in before deploying for real

- [ ] `data/hmm/evades_profiles.hmm` — your pressed HMM library
- [ ] `data/foldseek/evades_structures_db*` — your Foldseek DB of 268 structures
- [ ] `data/downloads/*` — the four bulk-download files
- [ ] `frontend/explore/` — the pre-rendered Explore pages (`generator/export_static.py`; see `generator/README.md`)
- [ ] `.env` with `DOMAIN=your.real.domain` — see "Deploying to a public server"

CORS and HTTPS are both handled by `docker-compose.prod.yml` (below) —
nothing to hand-edit in `backend/app/main.py`.

## Deploying to a public server

Nothing about this repo is unusual — it's meant to be portable to any
VM. [Hetzner Cloud](https://www.hetzner.com/cloud/) is the recommended
option: a CX22 (2 vCPU/4GB/40GB, ~€3.79/mo) covers low/no concurrent
traffic; a CX32 (4 vCPU/8GB, ~€7.55/mo) comfortably runs 2 worker
replicas in parallel — see "Handling concurrent requests" above for
sizing beyond that.

1. **Create the server.** Sign up, add an SSH key, create a CX22 or
   CX32 instance (Ubuntu 24.04 image). Note its IP.
2. **Get a domain and point it at the server.** Buy one anywhere, add
   an A record to the VM's IP. DNS propagation can take minutes to
   hours — do this early so it's ready by step 6.
3. **SSH in and install Docker:**
   ```bash
   ssh root@<server-ip>
   curl -fsSL https://get.docker.com | sh
   ```
4. **Get the code onto the server:**
   ```bash
   git clone git@github.com:Khalimat/evades-webapp.git
   cd evades-webapp
   ```
   (needs a deploy key or token if the repo is private — GitHub's docs
   cover that; simplest is generating a new SSH key on the server and
   adding it to the repo's Deploy keys.)
5. **Move the data that isn't in git**, from your Mac:
   ```bash
   rsync -avz data/hmm data/foldseek data/downloads frontend/explore \
     root@<server-ip>:~/evades-webapp/data/  # adjust destination per dir — see note below
   ```
   `data/hmm/`, `data/foldseek/`, `data/downloads/`, and
   `frontend/explore/` are all gitignored (large generated/scientific
   artifacts, not source). `frontend/explore/` goes to
   `evades-webapp/frontend/explore/`, not under `data/` — run the
   `rsync` per-directory to its matching path, or `tar czf - data
   frontend/explore | ssh root@<server-ip> 'cd evades-webapp && tar
   xzf -'` to move everything in one shot.
6. **Configure the domain:**
   ```bash
   cp .env.example .env
   # edit .env: DOMAIN=your.real.domain
   ```
7. **Open the firewall** (Hetzner Cloud Firewall, or `ufw` on the
   server) for ports **22, 80, 443** only — nothing else needs to be
   public.
8. **Bring it up:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
   This adds [Caddy](https://caddyserver.com/) in front of `nginx`,
   which automatically requests and renews a Let's Encrypt cert for
   `DOMAIN` (needs step 2's DNS to have propagated first), and sets
   `CORS_ORIGINS=https://$DOMAIN` on the `api` container. Check
   `docker compose ps` and `docker compose logs caddy`, then visit
   `https://your.real.domain`.

For local dev, keep using plain `docker compose up --build` (no
`-f docker-compose.prod.yml`) — that's unaffected by any of this.

The only optional extra step is migrating the Postgres volume if you
want job history to persist across the move (`pg_dump`/`pg_restore`)
— job records are just bookkeeping, not scientific data, so this is
skippable.
