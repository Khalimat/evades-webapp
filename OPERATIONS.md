# Operations — accessing and updating the live server

Reference for the deployed instance. See `README.md` for setting up a
*new* server from scratch — this is about the one that's already up.

## Current deployment

- **Server**: Hetzner Cloud, CX23 (2 vCPU / 4GB / 40GB), Ubuntu 24.04
- **IP**: `167.233.198.65` (check the server's page in the
  [Hetzner console](https://console.hetzner.cloud/) if this ever
  changes — e.g. after recreating the server)
- **URL**: `https://evades.app` — a real domain with an A record
  pointed at the IP above; Caddy holds its Let's Encrypt cert. This is
  set by `DOMAIN=` in `.env` on the server, and the Caddyfile serves
  only that one name — the old `167-233-198-65.sslip.io` address no
  longer has a cert and fails the TLS handshake. To change the domain
  again, see "Changing the domain" below.
- **Firewall**: only ports 22 (SSH), 80 (HTTP, needed for Let's
  Encrypt), 443 (HTTPS) are open.
- **Repo**: private, cloned via HTTPS with a GitHub personal access
  token cached in `~/.git-credentials` on the server (`git config
  --global credential.helper store` was run once during setup, so
  `git pull` doesn't re-prompt).

## Accessing the server

```bash
ssh root@167.233.198.65
cd evades-webapp
```

Your Mac's SSH key (`~/.ssh/id_ed25519`) is what authenticates you —
nothing else needed.

## Every command below needs both `-f` flags

The production stack uses an overlay file (`docker-compose.prod.yml`)
that adds Caddy (HTTPS) and sets `CORS_ORIGINS` on `api`. Compose only
knows about services/settings in whichever files you pass it — leaving
off `-f docker-compose.prod.yml` makes it act as if Caddy doesn't
exist and CORS isn't overridden. **Always run compose commands as:**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml <command>
```

Consider adding a shell alias on the server to save typing:
```bash
echo "alias dcp='docker compose -f docker-compose.yml -f docker-compose.prod.yml'" >> ~/.bashrc
source ~/.bashrc
# then just: dcp ps, dcp logs api, dcp restart nginx, etc.
```
(The examples below spell it out in full so they work whether or not
you've set the alias up.)

## Updating the code

Whenever `main` has new commits you want live:

```bash
cd ~/evades-webapp
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`--build` only actually rebuilds images whose Dockerfile/context
changed, so this is cheap to run even when nothing changed there.
Containers that didn't change are left running (no downtime for them).

## Updating the data (structures, HMM/Pfam library, Explore pages)

Anything under `data/` or `frontend/explore/` is gitignored — it never
comes from `git pull`, it has to be pushed from your Mac each time it
changes:

```bash
# from your Mac, in the repo root
cd ~/Desktop/evades-webapp
tar czf - data/hmm data/foldseek data/downloads frontend/explore | \
  ssh root@167.233.198.65 'cd evades-webapp && tar xzf -'
```

If you only changed one of those directories (e.g. just regenerated
`frontend/explore/` after an `EVADES.json` update), narrow the `tar`
command to just that path — no need to re-send everything.

**`data/foldseek/` (the built DB) and `data/downloads/predicted_structures.tar.gz`
/ `frontend/explore/` intentionally come from different structure sets**
— see "Monomer vs. multimer structures" in `data/README.md` before
touching either. The sync command above only ever needs the *built*
`data/foldseek/evades_structures_db*`, not the monomer source files
(`data/foldseek_monomer_structures/` stays Mac-only, same as any other
build input).

**If you changed the underlying dataset** (new/updated proteins,
structures, etc.), regenerate `frontend/explore/` and the Foldseek DB
on your Mac first — see `generator/README.md` for the full pipeline,
and note the footgun documented there: always re-run the full
`update_proteins.py` → `update_pdb_blobs.py` →
`update_euk_virus_homolog_blobs.py` → `update_protein_pfams.py` →
`update_secondary_structure_blobs.py` chain together, never
`update_proteins.py` alone, or you'll silently wipe the structure/
homolog/secondary-structure blobs for every protein (this happened
once already, see git log).

No container restart is needed after syncing data — `data/` is a bind
mount the containers read live, and `frontend/explore/` is served
directly by nginx from disk.

## Changing the domain

```bash
ssh root@167.233.198.65
cd evades-webapp
nano .env   # update DOMAIN=
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Point the new domain's DNS A record at `167.233.198.65` *before*
doing this, or Caddy can't get a cert for it. Caddy will automatically
request a fresh Let's Encrypt certificate for the new `DOMAIN` value.

## Useful commands

```bash
# Status of everything
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -a

# Logs for one service (add --tail 50, or -f to follow live)
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs api

# Restart one service without rebuilding
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx

# Scale workers for more concurrent searches (see README's "Handling
# concurrent requests" for sizing — this server's 2 vCPUs comfortably
# run 1 replica; don't go above 1 here without resizing the server)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale worker=2

# Disk usage sanity check
df -h
docker system df
```

## Known gotchas (already hit these once — here's the fix if they recur)

**`api` container shows `Exited` right after `up -d`.** Postgres
occasionally isn't fully ready yet on first boot when `api` tries to
connect (a `depends_on` only waits for the container to *start*, not
for Postgres to actually accept connections). Fix:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
```

**502 Bad Gateway after recreating `api` or `worker`.** nginx resolves
the `api`/`worker` container's internal IP once and caches it — if
that container gets recreated (new IP) without nginx also restarting,
nginx keeps trying the dead IP. Fix: `docker compose ... restart
nginx` after any `up -d --build` that touches `api`.

**Freeing disk space**, if `docker system df` shows it filling up
(old images pile up after repeated `--build`s):
```bash
docker image prune -f
```

## Housekeeping not yet done

- No automated backups (skipped deliberately for cost — see README's
  "Handling concurrent requests"/deploy section for the reasoning;
  everything here is reproducible from git + your Mac's copies of
  `data/`/`frontend/explore/`).
- No monitoring/alerting set up — if the server goes down, you'll only
  notice by checking it.
- Cookie-consent banner on Explore pages (leftover EBI framework JS)
  is cosmetic-only, not yet removed.
