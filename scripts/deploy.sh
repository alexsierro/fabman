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
    # Version: commit date of HEAD, numbered by its rank among that day's commits
    day=$(git log -1 --format=%cd --date=format:%Y-%m-%d)
    count=$(git log --format=%cd --date=format:%Y-%m-%d | grep -c "^$day$")
    echo "$day.$count" > VERSION

    echo "==> Pulling image"
    docker compose -f docker-compose.prod.yml pull web

    echo "==> Restarting services"
    if ! docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 180; then
        docker compose -f docker-compose.prod.yml ps
        docker compose -f docker-compose.prod.yml logs --tail=100 web nginx
        return 1
    fi

    # nginx resolves web at config load; a recreated container can have a new IP.
    echo "==> Reloading nginx upstream addresses"
    docker compose -f docker-compose.prod.yml exec -T nginx nginx -t
    docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload

    echo "==> Cleaning old images"
    docker image prune -f

    echo "==> Deployed $(git rev-parse --short HEAD)"
}

main "$@"
exit
