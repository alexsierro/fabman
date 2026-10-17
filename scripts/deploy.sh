#!/usr/bin/env bash
# Deploys the latest main on the production server.
# Called by GitHub Actions over SSH, as the forced command of the deploy key.
#
# Everything is wrapped in main() so bash reads the whole file before running it:
# `git pull` may rewrite this script while it is executing.

set -euo pipefail

main() {
    cd "$(dirname "$(readlink -f "$0")")/.."

    echo "==> Pulling code"
    git pull --ff-only origin main

    echo "==> Pulling image"
    docker compose -f docker-compose.prod.yml pull web

    echo "==> Restarting services"
    docker compose -f docker-compose.prod.yml up -d

    echo "==> Cleaning old images"
    docker image prune -f

    echo "==> Deployed $(git rev-parse --short HEAD)"
}

main "$@"
exit
