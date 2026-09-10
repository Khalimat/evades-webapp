# EVADES web app

Self-hosted companion site for the EVADES database of anti-defence
proteins (ADPs). It offers three things:

- **Browse** — one page per ADP, pre-rendered as static HTML from the
  EVADES dataset (see `generator/README.md`).
- **Analyse** — search your own data against EVADES: profile HMM
  search (HMMER `hmmsearch`) against the EVADES HMM library, and
  structure search (Foldseek) against the EVADES structure set.
- **Download** — bulk data files (sequences, metadata, structures, HMM
  profiles).

The site has no runtime dependency on EBI infrastructure. It is a
small set of containers defined in `docker-compose.yml`: run locally
with Docker Compose for development, deployed to Kubernetes
(EMBL-EBI) for production.

## Architecture

Every box below is one container. `docker-compose.yml` is the
authoritative list.

| Component | Role |
|---|---|
| **nginx** | The only entry point. Routes by URL path: the static frontend, the `/explore/` pages, the `/downloads/` files, and `/api/` to the api container. |
| **frontend** | Static HTML/JS (`frontend/`), served straight from disk by nginx. No build step. |
| **explore pages** | Pre-rendered per-protein HTML (`frontend/explore/`), generated offline — not built at deploy time. Served by nginx. |
| **api** (FastAPI) | Accepts an upload, validates it, and puts a job on the queue. Returns a job id immediately. Never runs HMMER or Foldseek itself; reads job status and results back from Postgres. |
| **redis** | Holds the [RQ](https://python-rq.org/) job queue. Decouples "user clicked Run" from "a search is actually running". |
| **worker** | The only place HMMER and Foldseek run. Takes a job off the queue, runs the tool against the databases in `/data`, writes the parsed result to Postgres. This is the piece you scale for concurrency. |
| **postgres** | Job bookkeeping only — job id, type, status, result JSON. No scientific data. Reproducible and safe to lose. |
| **/data** | Reference data mounted read-only into api / worker / nginx: the pressed HMM library, the Foldseek database, and the bulk-download files. Not in git — see [Reference data](#reference-data-not-in-git). |

```mermaid
flowchart TD
    B([Browser])
    N[nginx]
    F[static frontend]
    E[explore pages]
    A[api — FastAPI]
    Q[[redis — RQ queue]]
    W[worker — HMMER + Foldseek]
    P[(postgres — job records)]
    D[/"data: HMM DB, Foldseek DB, downloads"/]

    B --> N
    N -->|"/"| F
    N -->|"/explore/"| E
    N -->|"/downloads/"| D
    N -->|"/api/"| A
    A -->|enqueue| Q
    Q -->|dequeue| W
    W -->|read| D
    W -->|"write result"| P
    A -->|"read status / result"| P
```

A search, end to end:

1. The browser uploads a FASTA (HMM search) or a PDB/mmCIF file
   (structure search) to `POST /api/search/hmm` or
   `POST /api/search/structure`.
2. `api` validates the file, saves it to the shared uploads volume,
   enqueues a job on redis, writes a `queued` row to Postgres, and
   returns a job id right away.
3. A free `worker` picks up the job, runs `hmmsearch` or `foldseek`
   against `/data`, and writes the result to Postgres.
4. The browser polls `GET /api/jobs/{id}` until the status is
   `finished` (or `failed`), then renders the result.

Step 2 returns instantly no matter how busy the system is, so
submissions never block or fail under load — they queue. How many run
in parallel rather than wait depends only on the number of `worker`
replicas.

## Quick start (local)

1. Put the reference data in place — see `data/README.md` and
   [Reference data](#reference-data-not-in-git).
2. `cp .env.example .env` (the defaults are fine for local dev).
3. `docker compose up --build`
4. Open `http://localhost:8080`.

To put this online at **`https://www.ebi.ac.uk/finn-srv/evades/`**, see
[Going live](#going-live-kubernetes-at-wwwebiacukfinn-srvevades).

Backend tests and lint:

```bash
cd backend
pip install -r requirements-dev.txt
ruff check . && pytest
```

CI (`.github/workflows/ci.yml`) runs the same checks plus a Docker
image build on every push and pull request.

## Reference data (not in git)

Four artifacts are generated or scientific data, not source. They are
gitignored and delivered separately from the code:

| Path | What | Produced by |
|---|---|---|
| `data/hmm/evades_profiles.hmm*` | Pressed HMM profile library | `data/README.md` |
| `data/foldseek/evades_structures_db*` | Foldseek database (268 structures) | `foldseek createdb`, per `data/README.md` |
| `data/downloads/*` | The four bulk-download files | dataset export |
| `frontend/explore/` | Pre-rendered Browse pages | `generator/export_static.py` — see `generator/README.md` |

For local development, drop each at the path above. For the
Kubernetes deployment they need an **out-of-band delivery path** —
an object store the pods sync from, or a pre-populated volume —
because there is no SSH access to the running service. Wiring this up
is the main open item for the production move.

Updates to this data are expected roughly once a year and are
additive (more entries), not functional changes. Regenerate
`frontend/explore/` and the Foldseek DB **together** from the dataset
— see the blob-wipe footgun documented in `generator/README.md`.

## Going live (Kubernetes, at `www.ebi.ac.uk/finn-srv/evades/`)

### How the containers map to Kubernetes

The `docker-compose.yml` service graph maps directly onto Kubernetes
resources:

| Compose service | Kubernetes |
|---|---|
| nginx | Deployment + Service, behind the cluster Ingress (TLS terminated at the Ingress — no Caddy needed) |
| frontend / explore pages | files served by nginx; baked into the nginx image or mounted from a volume |
| api | Deployment + Service |
| worker | Deployment with `replicas: N` — the concurrency knob (the equivalent of Compose's `--scale worker=N`) |
| redis | Deployment + Service (ephemeral — the queue does not need to survive a restart) |
| postgres | StatefulSet + PVC, or a managed database |
| `./data` bind mount | ReadOnlyMany PVC or object-store sync, populated out of band — see [Reference data](#reference-data-not-in-git) |
| `CORS_ORIGINS` (`.env`) | env var on the api Deployment, set to `https://www.ebi.ac.uk` |

### The URL prefix

The app will be served under a path, `/finn-srv/evades/`, not at a
domain root. `www.ebi.ac.uk` is a front proxy that forwards that path
to the service. It can do this in one of two ways, and the first
question to settle with the EBI web team is **which**:

- **Prefix stripped** (recommended) — the proxy removes
  `/finn-srv/evades` before forwarding, so the backend still sees
  requests at `/`. nginx needs **no changes**; only the browser-facing
  HTML has to carry the prefix (steps 2–3).
- **Prefix preserved** — the backend receives the full
  `/finn-srv/evades/...` path and nginx must be taught about it
  (step 4).

Either way, `frontend/index.html` and the Explore pages must be built
for the new location, because they emit absolute URLs.

### Steps

1. **Settle the prefix behaviour** with the EBI web team (see above).
   Everything below follows from that answer.
2. **Set the frontend base path.** In `frontend/index.html`, change
   `<base href="/">` to `<base href="/finn-srv/evades/">`. Every link
   in `index.html` / `app.js` is relative, so that is the only change
   there.
3. **Regenerate the Explore pages for the new path.** In
   `generator/export_static.py` set
   `SCRIPT_PREFIX = "/finn-srv/evades/explore/"` (the "back to home"
   link is derived from it automatically), then re-run the generator
   — see `generator/README.md`. The generated HTML bakes in absolute
   paths, so a build made for local `/explore/` will 404 its CSS and
   links under `/finn-srv/evades/`.
4. **Only if the prefix is preserved:** in `nginx/default.conf`, move
   every `location` under the prefix
   (`/finn-srv/evades/`, `/finn-srv/evades/api/`,
   `/finn-srv/evades/downloads/`, `/finn-srv/evades/explore/`),
   keeping `proxy_pass http://api:8000/api/;` as-is. If the prefix is
   stripped, leave this file untouched.
5. **Set CORS.** `CORS_ORIGINS=https://www.ebi.ac.uk` on the api
   Deployment.
6. **Create the Kubernetes resources** per the mapping table above:
   Deployments + Services for nginx, api, worker, redis; StatefulSet +
   PVC (or a managed DB) for postgres; a ReadOnlyMany PVC (or
   object-store sync) for `/data`; and the Ingress / front-proxy route
   for `/finn-srv/evades/`.
7. **Load the data that isn't in git** — the `/data` contents and
   `frontend/explore/` — via the object-store or populated-volume
   mechanism the team sets up (there is no SSH). See
   [Reference data](#reference-data-not-in-git).
8. **Deploy** by merging to `main`: CI builds the images, the rollout
   picks them up.
9. **Verify:** `https://www.ebi.ac.uk/finn-srv/evades/` loads;
   `…/api/health` returns `{"status": "ok"}`; a test HMM search and a
   test structure search both complete; `…/explore/protein_list/`
   renders with styling; the four `…/downloads/*` files serve.

### Operational model

- **No SSH, no in-place edits.** All changes ship through git:
  PR → review → merge → CI builds images → rollout.
- **Concurrency.** Each job is capped at 2 threads
  (`hmmsearch --cpu 2`, `foldseek --threads 2`), so replicas don't
  fight over every core. Rule of thumb: **worker CPU ≈ 2 × the number
  of searches you want running genuinely in parallel.** Past that,
  jobs wait in the queue for a few seconds rather than failing. One
  worker replica covers the expected traffic; raise `replicas` if that
  changes.
- **State.** Only Postgres and the uploads volume hold state, and
  neither holds scientific data — job rows are bookkeeping, uploads
  are transient. Everything else is reproducible from git plus the
  reference data. Backups are optional.

`OPERATIONS.md` describes the current interim single-VM deployment; it
will be superseded once this is in place.
