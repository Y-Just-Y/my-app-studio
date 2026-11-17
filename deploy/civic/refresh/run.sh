#!/usr/bin/env bash
# A bounded, key-free lexical job on the existing Civic host only.
set -euo pipefail
CIVIC_REFRESH_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CIVIC_PROJECT_DIR=$(cd -- "$CIVIC_REFRESH_DIR/../../.." && pwd)
CIVIC_JOB_NAME=civic-lexical-refresh
if [[ -n ${DOCKER_HOST:-} || -n ${DOCKER_CONTEXT:-} ]] || \
   [[ $(hostname) != newark-civic-pulse ]] || \
   [[ ! -f /etc/newark-civic-pulse-host ]] || \
   [[ $(cat /etc/newark-civic-pulse-host) != "$CIVIC_PROJECT_DIR" ]]; then
  echo "Refusing a different host or Docker context." >&2
  exit 2
fi
if [[ $(docker context inspect --format '{{.Endpoints.docker.Host}}') != unix:///var/run/docker.sock ]]; then
  echo "Refusing a nonlocal Docker endpoint." >&2
  exit 2
fi
if [[ ${1:-} == --cleanup ]]; then
  if [[ $(docker inspect --format '{{index .Config.Labels "org.newarkcivic.refresh"}}' "$CIVIC_JOB_NAME" 2>/dev/null || true) == lexical ]]; then
    docker container rm --force "$CIVIC_JOB_NAME" >/dev/null
  fi
  exit 0
fi
if [[ $# -ne 0 ]]; then
  echo "Usage: run.sh [--cleanup]" >&2
  exit 2
fi
CIVIC_RUNNING_IMAGE=$(docker inspect --format '{{.Image}}' civic-pulse-app-1)
CIVIC_RUNTIME_VOLUME=$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/app/runtime"}}{{.Name}}{{end}}{{end}}' civic-pulse-app-1)
if [[ ! $CIVIC_RUNNING_IMAGE =~ ^sha256:[0-9a-f]{64}$ ]] || \
   [[ $CIVIC_RUNTIME_VOLUME != civic-pulse_runtime ]] || \
   [[ $(docker inspect --format '{{.State.Running}}' civic-pulse-app-1) != true ]]; then
  echo "The expected Civic application and runtime volume are not running." >&2
  exit 2
fi
# Use the approved running image, not a mutable build tag. Do not pass .env or a key.
docker run --rm --name "$CIVIC_JOB_NAME" \
  --label org.newarkcivic.refresh=lexical \
  --network bridge --user 10001:10001 --read-only --cap-drop ALL \
  --security-opt no-new-privileges --memory 192m --cpus 0.35 --pids-limit 64 \
  --mount "type=volume,source=$CIVIC_RUNTIME_VOLUME,target=/app/runtime" \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --env CIVIC_REFRESH_SCHEDULE=nightly --entrypoint python \
  "$CIVIC_RUNNING_IMAGE" /app/civic_refresh.py \
  --database /app/runtime/civic.sqlite3 --limit 5
