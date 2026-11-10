# Separate Civic host

This package is for a **new, separate Ubuntu 24.04 DigitalOcean Droplet** serving
`civic.lwdgyasteri.com`. It does not deploy to or change the existing LWDGY ASTERI
host. Creating the Droplet, its billing choice, DNS, cloud firewall and SSH access
are separate user-approved operations; this directory does none of those things.

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

## Local validation boundary

`docker compose config --quiet` can validate interpolation and Compose structure
without a running Docker daemon, using a private dummy env file containing no
real credentials. It does not prove the image builds, the container fits in RAM,
DNS/TLS works or the app is live. Those results require the new host and must be
recorded from actual execution.

Primary references: [Docker's Ubuntu installation guide](https://docs.docker.com/engine/install/ubuntu/),
[Caddy with Docker Compose](https://caddyserver.com/docs/running#docker-compose),
and [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
