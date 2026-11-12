#!/usr/bin/env bash
# Run on the manager after loading images and joining both workers.
set -euo pipefail
cd "$(dirname "$0")"
test "$(docker info --format '{{.Swarm.ControlAvailable}}')" = true
test "$(docker node ls --format '{{.ID}}' | wc -l)" -eq 3
if [ ! -f .cluster.env ]; then
  umask 077
  printf 'POSTGRES_PASSWORD=%s\n' "$(python3 -c 'import secrets; print(secrets.token_hex(24))')" > .cluster.env
fi
set -a
source .cluster.env
REGISTRY=supinfo.local
POSTGRES_USER=postgres
POSTGRES_DB=postgres
set +a
docker node update --label-add voting.data=true "$(docker info --format '{{.Swarm.NodeID}}')" >/dev/null
# Offline laboratory: matching tagged images are loaded on all nodes beforehand.
docker stack config -c docker-compose.swarm.yml >/dev/null
docker stack deploy --resolve-image never -c docker-compose.swarm.yml voting
docker stack services voting
