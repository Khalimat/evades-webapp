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
- [ ] `frontend/explore/` — the pre-rendered Explore pages (`generator/export_static.py`; see `generator/README.md`)
- [ ] Swap `CORSMiddleware allow_origins=["*"]` in `backend/app/main.py` for your real domain
- [ ] Put this behind HTTPS (Caddy or nginx + certbot) once it has a public domain

## Deploying to a public server

Nothing about this repo is unusual — it's meant to be portable to any
VM (Hetzner, DigitalOcean, EMBL-EBI's Embassy Cloud, ...).

1. **Get a server.** A small VPS is plenty — HMMER/Foldseek searches
   are small per-request jobs, not the heavy one-time pipeline build
   in `generator/`. 2GB RAM / 2 vCPU is comfortable.
2. **Get a domain and point it at the server.** Buy one anywhere,
   then add an A record to the VM's IP. DNS propagation can take a
   few minutes to a few hours.
3. **Install Docker on the server:**
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
4. **Get the code onto the server** — push this repo to its remote,
   then `git clone` + check out the right branch on the server.
5. **Move the data that isn't in git.** `data/hmm/`, `data/foldseek/`,
   `data/downloads/`, and `frontend/explore/` are all gitignored
   (large generated/scientific artifacts, not source) and need to
   travel separately — `rsync`/`scp` them across. For `frontend/explore/`
   specifically, it's easiest to copy the already-built output rather
   than re-running the whole `generator/` pipeline on the server; only
   re-run that when the underlying protein dataset actually changes.
6. **Tighten CORS and add HTTPS** — the two checklist items above.
   [Caddy](https://caddyserver.com/) in front of (or instead of) the
   `nginx` container is the simplest way to get an auto-renewing
   Let's Encrypt cert with just a few lines of config.
7. **Bring it up:**
   ```bash
   docker compose up -d --build
   ```
   same as locally. Check `docker compose ps`, then hit the domain in
   a browser.

The only optional extra step is migrating the Postgres volume if you
want job history to persist across the move (`pg_dump`/`pg_restore`)
— job records are just bookkeeping, not scientific data, so this is
skippable.
