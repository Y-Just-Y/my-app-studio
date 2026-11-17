#!/usr/bin/env bash
# Install only after reviewing and deploying the Civic refresh CLI.
set -euo pipefail
if [[ $EUID -ne 0 || ${1:-} != --enable-nightly || $# -ne 1 ]]; then
  echo "Usage: sudo bash install.sh --enable-nightly" >&2
  exit 2
fi
CIVIC_REFRESH_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CIVIC_PROJECT_DIR=$(cd -- "$CIVIC_REFRESH_DIR/../../.." && pwd)
if [[ $(hostname) != newark-civic-pulse ]] || \
   [[ $CIVIC_PROJECT_DIR != /opt/newark-civic-pulse ]] || \
   [[ ! -f /etc/newark-civic-pulse-host ]] || \
   [[ $(cat /etc/newark-civic-pulse-host) != "$CIVIC_PROJECT_DIR" ]] || \
   [[ -n ${DOCKER_HOST:-} || -n ${DOCKER_CONTEXT:-} ]]; then
  echo "Refusing installation outside the marked Civic host checkout." >&2
  exit 2
fi
if [[ $(docker context inspect --format '{{.Endpoints.docker.Host}}') != unix:///var/run/docker.sock ]]; then
  echo "Refusing a nonlocal Docker endpoint." >&2
  exit 2
fi
# The manual help check cannot fetch a source or load an API key.
docker exec civic-pulse-app-1 python /app/civic_refresh.py --help >/dev/null
chmod 755 "$CIVIC_REFRESH_DIR/run.sh"
install -m 644 "$CIVIC_REFRESH_DIR/civic-refresh.service" /etc/systemd/system/civic-refresh.service
install -m 644 "$CIVIC_REFRESH_DIR/civic-refresh.timer" /etc/systemd/system/civic-refresh.timer
systemd-analyze verify /etc/systemd/system/civic-refresh.service /etc/systemd/system/civic-refresh.timer
systemctl daemon-reload
systemctl enable --now civic-refresh.timer
systemctl list-timers civic-refresh.timer --no-pager
printf 'Nightly lexical refresh enabled. Set CIVIC_REFRESH_SCHEDULE=nightly in the deployment configuration for the public configured label.\n'
