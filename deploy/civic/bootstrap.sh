#!/usr/bin/env bash
# Run only on the separately authorized new Civic host. Never run on Asteri.
set -euo pipefail

if [[ ${1:-} != --new-civic-host || -z ${2:-} ]]; then
  echo "Usage: sudo ./bootstrap.sh --new-civic-host NEW_DROPLET_IPV4" >&2
  exit 2
fi
if [[ $EUID -ne 0 ]]; then
  echo "Run this reviewed script as root on the NEW Civic host." >&2
  exit 2
fi
if [[ -n ${DOCKER_HOST:-} || -n ${DOCKER_CONTEXT:-} ]]; then
  echo "Refusing a remote or alternate Docker context. Use this host's local Docker." >&2
  exit 2
fi

CIVIC_SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CIVIC_REPO_ROOT=$(cd -- "$CIVIC_SCRIPT_DIR/../.." && pwd)
CIVIC_ENV_PATH="$CIVIC_SCRIPT_DIR/.env"
CIVIC_HOST_MARKER=/etc/newark-civic-pulse-host
CIVIC_EXPECTED_IPV4=$2

# The distro file is root-owned on the new machine; it is not a downloaded script.
. /etc/os-release
if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 24.04 ]]; then
  echo "This bootstrap is for a new Ubuntu 24.04 host." >&2
  exit 2
fi
if [[ ! -f $CIVIC_ENV_PATH || -L $CIVIC_ENV_PATH ]]; then
  echo "Create the private deploy/civic/.env file before bootstrapping." >&2
  exit 2
fi
python3 - "$CIVIC_ENV_PATH" "$CIVIC_EXPECTED_IPV4" <<'PY'
import ipaddress
from pathlib import Path
import stat
import sys

path = Path(sys.argv[1])
ipaddress.IPv4Address(sys.argv[2])
if stat.S_IMODE(path.stat().st_mode) & 0o077:
    raise SystemExit("Private deploy/civic/.env must have mode 600 or stricter.")
if path.stat().st_uid != 0:
    raise SystemExit("The deployment env file must be owned by root.")
values = {}
for line in path.read_text().splitlines():
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    key, separator, value = line.partition("=")
    if not separator or key in values:
        raise SystemExit("Use one KEY=value per line in the deployment env file.")
    values[key] = value
secret = values.get("APP_SECRET", "")
if len(secret.encode()) < 32 or secret.startswith("replace-"):
    raise SystemExit("Set a private random APP_SECRET of at least 32 bytes.")
if values.get("CIVIC_AI_ENABLED", "0") not in {"0", "1"}:
    raise SystemExit("CIVIC_AI_ENABLED must be 0 or 1.")
if values.get("CIVIC_AI_ENABLED", "0") == "1":
    key = values.get("OPENAI_API_KEY", "")
    if not key.startswith("sk-") or any(c.isspace() for c in key):
        raise SystemExit("AI mode needs a privately configured OpenAI API key.")
if any("$" in value for value in values.values()):
    raise SystemExit("Use literal values without dollar-sign interpolation.")
PY

if ! getent ahostsv4 civic.lwdgyasteri.com | awk '{print $1}' | \
  grep -Fxq -- "$CIVIC_EXPECTED_IPV4"; then
  echo "Point civic.lwdgyasteri.com to this NEW Droplet IPv4 first." >&2
  exit 2
fi

if [[ -e $CIVIC_HOST_MARKER ]]; then
  if [[ ! -f $CIVIC_HOST_MARKER || -L $CIVIC_HOST_MARKER ]] || \
    [[ $(cat -- "$CIVIC_HOST_MARKER") != "$CIVIC_REPO_ROOT" ]]; then
    echo "This host marker belongs to a different checkout; review it manually." >&2
    exit 2
  fi
elif ss -H -ltn | awk '$4 ~ /:(80|443)$/ {found=1} END {exit !found}'; then
  echo "Refusing to replace an existing service on port 80 or 443." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl --fail --silent --show-error \
    https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  CIVIC_ARCH=$(dpkg --print-architecture)
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $CIVIC_ARCH
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
fi

systemctl enable --now docker
if [[ $(docker context inspect "$(docker context show)" \
  --format '{{.Endpoints.docker.Host}}') != unix:///var/run/docker.sock ]]; then
  echo "Refusing a nonlocal Docker endpoint." >&2
  exit 2
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker exists without the Compose plugin; review that installation manually." >&2
  exit 2
fi
docker compose --env-file "$CIVIC_ENV_PATH" \
  -f "$CIVIC_SCRIPT_DIR/compose.yaml" config --quiet

# Write the marker before starting our own containers so a failed start can be retried.
printf '%s\n' "$CIVIC_REPO_ROOT" > "$CIVIC_HOST_MARKER"
chmod 0600 "$CIVIC_HOST_MARKER"
docker compose --env-file "$CIVIC_ENV_PATH" \
  -f "$CIVIC_SCRIPT_DIR/compose.yaml" up --build -d --wait --wait-timeout 180
docker compose --env-file "$CIVIC_ENV_PATH" \
  -f "$CIVIC_SCRIPT_DIR/compose.yaml" exec -T app \
  python civic_import.py --limit 5
echo "Civic app started. Check https://civic.lwdgyasteri.com/health and /api/civic/status."
echo "No embedding/generation requests were made by this bootstrap."
