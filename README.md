# EVADES web app

Self-hosted companion site for the EVADES database: bulk downloads +
an "Analyse" tab (HMM search via HMMER, structure search via
Foldseek). No dependency on EBI infrastructure — runs entirely in
Docker Compose, portable to any VM (Hetzner, DigitalOcean, or later
EMBL-EBI's Embassy Cloud).

## Architecture

```
 browser
    |
  nginx  (reverse proxy, port 8080)
    |
    +--> static frontend (HTML/JS)
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
enqueues jobs. The `worker` container is the only place those tools
run. This keeps the public-facing API image small and means you can
scale workers independently later if load grows.

## Quick start (local)

1. Build the databases — see `data/README.md`.
2. `cp .env.example .env` and adjust if needed (defaults work for local dev).
3. `docker compose up --build`
4. Visit `http://localhost:8080`

## What to fill in before deploying for real

- [ ] `data/hmm/evades_profiles.hmm` — your pressed HMM library
- [ ] `data/foldseek/evades_structures_db*` — your Foldseek DB of 268 structures
- [ ] `data/downloads/*` — the four bulk-download files
- [ ] Swap `CORSMiddleware allow_origins=["*"]` in `backend/app/main.py` for your real domain
- [ ] Put this behind HTTPS (Caddy or nginx + certbot) once it has a public domain

## Moving to Embassy Cloud (or any other VM) later

Nothing changes. Provision a VM, install Docker + Docker Compose,
`git clone` this repo, copy your `data/` contents across, `docker
compose up -d`. Point DNS at the new IP. The only manual step is
migrating the Postgres volume if you want job history to persist
(`pg_dump`/`pg_restore`), which is optional — job records are just
bookkeeping, not scientific data.
