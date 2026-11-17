# Separate Civic host

This package uses a **separate Ubuntu 24.04 DigitalOcean Droplet** for
`civic.lwdgyasteri.com` and the personal portfolio at
`derrickparker.lwdgyasteri.com`. Both addresses use the same application and
existing host. It does not deploy to or change the LWDGY ASTERI application host.
Creating a Droplet, its billing choice, DNS, cloud firewall and SSH access are
separate user-approved operations; this directory does none of those things.

The authorized infrastructure ceiling is **$6/month**. Select a current plan at
or below that price before creation. No paid backups, extra volumes or other
optional charges are assumed. API usage is a separate cost. The intended target
has 1 GB RAM and one CPU: the app is limited to 512 MB, Caddy to 128 MB, with the
remaining memory for the host and Docker. Measure the actual host before calling
this a production-capacity result. No local language model runs on this host.

## What runs

- FastAPI, one application process, internal port 8000.
- Caddy HTTPS reverse proxy; only host TCP ports 80 and 443 are published.
- A persistent Docker volume for the separate account and civic SQLite files.
- Manual, bounded Python ETL from the public Newark feed.

Rust and NATS are deferred for this first small checked import. No broker is
installed or exposed. Semantic embedding requests require explicit API setup and
the separate `civic_embed.py --confirm-api-usage` command; bootstrap does not run
that command. Source search can be inspected while AI mode is disabled.

There was no root Dockerfile in this checkout. Compose therefore builds from an
inline Dockerfile with explicit source copies, a non-root UID 10001, and immutable
official Python/Caddy image digests verified on November 10, 2026. The application
container has a read-only root filesystem; its runtime volume and temporary
directory are writable. A one-shot initializer sets only this package's named
volume directory ownership for UID 10001. It does not change arbitrary host data.
The application accepts forwarded client/protocol headers only on its unpublished
container port, reached through the dedicated Caddy network. Do not publish app
port 8000 or attach untrusted services to that network.

## Prepare the new machine

1. Create the approved separate Droplet with SSH-key access. Independently verify
   its SSH host fingerprint before connecting. Keep the existing Asteri server
   and DNS records separate.
2. Set the `civic.lwdgyasteri.com` A record to the new Droplet's IPv4. Remove or
   correct any conflicting AAAA record before certificate issuance. Allow public
   TCP 80/443 in a DigitalOcean cloud firewall and restrict SSH to your chosen
   administrator address. Bootstrap does not modify SSH or enable a firewall,
   so it cannot silently lock you out. Docker-published ports can bypass UFW;
   rely on the cloud firewall and the declared published ports here.
3. Copy the reviewed application checkout to this new host. The build includes
   `app`, `studio_tools`, requirements and the two civic CLIs. Keep runtime data,
   local environments, Git history and credentials out of the build context.
4. Create `deploy/civic/.env` privately on that host, owned by root with mode 600.
   It is ignored by Git. Use literal, unquoted `KEY=value` entries; do not paste
   the resulting file into chat, issues or logs.

   ```dotenv
   APP_SECRET=replace-with-a-private-random-value-of-at-least-32-bytes
   OPENAI_API_KEY=
   OPENAI_CHAT_MODEL=gpt-5-mini
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   CIVIC_AI_ENABLED=0
   ```

   Generate the real application secret privately with
   `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'` and replace the
   example. Add your OpenAI project key privately. Set `CIVIC_AI_ENABLED=1` only
   when you intend to permit paid model requests; that does not build an embedding
   index by itself. Do not commit keys or SQLite files.

## Run after reviewing the package

On the **new Civic host**, from `deploy/civic`:

```sh
sudo bash bootstrap.sh --new-civic-host NEW_DROPLET_IPV4
```

The script checks Ubuntu, DNS, private configuration and occupied web ports before
installation. It installs Docker from Docker's signed official Ubuntu repository
only if Docker is absent; it does not replace an existing engine or remove
conflicting packages. It records this checkout in a dedicated host marker and
can be rerun for the same checkout. It starts only this Compose project, waits for
the application's production-mode health check, then imports at most five
meetings from the public API. It never runs a paid model request.

The first certificate requires working DNS and inbound 80/443. Check:

```sh
curl --fail https://civic.lwdgyasteri.com/health
curl --fail https://civic.lwdgyasteri.com/api/civic/status
```

The health result must report `production`. Check the actual homepage, source
links, chat state and a supported/unsupported question in the browser too. A
successful health result alone does not establish completed RAG behavior.

For subsequent manual operations, run from this directory:

```sh
sudo docker compose --env-file .env -f compose.yaml ps
sudo docker compose --env-file .env -f compose.yaml exec -T app python civic_import.py --limit 5
```

If you intentionally enable embeddings, use the separately documented bounded
embedding command and account budget before a real model test. If a key or quota
fails, correct it and make an explicit retry; do not loop model requests.

The `runtime` and Caddy certificate volumes persist across ordinary container
recreation. Back them up privately before an upgrade. `docker compose down` keeps
them; `down --volumes` deletes them and must not be used as routine cleanup.
Check actual import/retrieval persistence after an ordinary restart.

## Personal portfolio address

The owner authorized `derrickparker.lwdgyasteri.com` on the existing Civic host.
Its A record must point to `143.110.239.142` before activating this Caddyfile.
The existing Civic host, application image, runtime volume, certificate volumes
and $6/month infrastructure budget are reused.

| Personal-domain path | Caddy behavior |
| --- | --- |
| `/` | Internally rewrite to `/portfolio`, keeping the personal address in the browser. |
| `/portfolio` and `/portfolio/*` | Proxy the public portfolio and case-study routes; strip a trailing slash before proxying. |
| `/static/portfolio.css` | Proxy the portfolio stylesheet. |
| Other paths | Return 302 to `https://civic.lwdgyasteri.com` with the original path and query. |

The personal-domain proxy sets both upstream `Host` and `X-Forwarded-Host` to the
fixed value `civic.lwdgyasteri.com`. Clients cannot select the upstream hostname.
The application's trusted host, `APP_ORIGIN`, authentication and CSRF checks stay
at the Civic origin. Chat, research and account links therefore return there;
the personal host serves the public portfolio. No source import or model request
is part of this proxy change.

After the DNS change is confirmed, validate the configuration with the pinned
Caddy image before replacing the proxy. The admin API is disabled, so activate
from this directory by recreating only Caddy:

```sh
sudo docker compose --env-file .env -f compose.yaml up -d --no-deps --no-build --force-recreate caddy
```

This keeps the application process and named volumes in place. Then verify
normal CA/hostname-checked HTTPS for the personal home, case study and stylesheet;
check that `/ask` and `/research` redirect to Civic, and confirm Civic production
health and the unchanged seven-source/eight-chunk/eight-vector status. Config
validation alone does not establish DNS, certificate issuance or live routing.

## Verified deployment · November 10, 2026

The initial deployment used application revision `65c0e4914d18` at
[civic.lwdgyasteri.com](https://civic.lwdgyasteri.com/), with
[chat](https://civic.lwdgyasteri.com/ask) and
[research](https://civic.lwdgyasteri.com/research). The separate Droplet is
`617873335`, IPv4 `143.110.239.142`, Ubuntu 24.04 in SFO3, at the approved
$6/month plan. No paid backup service or extra volume was added. The key and
application secret were transferred privately; no local accounts were copied.

Observed: normal CA/hostname validation passed for TLS 1.3; health reports
production; home/chat/research/status return 200. The live model returned the
November 5 record's scheduled 12:30 PM/Council Chamber with its expected source.
Anonymous import returns 401; chat without CSRF returns 403. See the
[public request receipt](../../docs/research/newark-hosted-check.json).

Seven sources/eight chunks/eight real embeddings survived an ordinary app
restart and the final container recreation. A read transaction and SQLite
`Connection.backup()` created a private snapshot, then restored it into a
separate temporary database. Integrity, source/chunk/version fingerprints,
vector mapping hashes and vector bytes matched; the restored index reported
8/8 compatible 1536-dimensional embeddings. The temporary restore was removed;
the private backup was retained. The live database and account database were
not replaced during this check. See the
[recovery receipt](../../docs/research/newark-recovery-check.json).

The measured app used about 44 MiB and Caddy 13 MiB at idle. These are observed
idle values, not a load test. A 1 GiB swap file uses the existing disk. Public
listeners are TCP 22/80/443, with no published application/database port.
The original Asteri host and existing root-domain records were not modified.

## Local validation boundary

`docker compose config --quiet` can validate interpolation and Compose structure
without a running Docker daemon, using a private dummy env file containing no
real credentials. It does not prove the image builds, the container fits in RAM,
DNS/TLS works or the app is live. Those results require the new host and must be
recorded from actual execution.

Primary references: [Docker's Ubuntu installation guide](https://docs.docker.com/engine/install/ubuntu/),
[Caddy with Docker Compose](https://caddyserver.com/docs/running#docker-compose),
[Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[mutually exclusive handlers](https://caddyserver.com/docs/caddyfile/directives/handle),
[internal rewrites](https://caddyserver.com/docs/caddyfile/directives/rewrite),
[path normalization](https://caddyserver.com/docs/caddyfile/directives/uri),
and [redirects](https://caddyserver.com/docs/caddyfile/directives/redir).
