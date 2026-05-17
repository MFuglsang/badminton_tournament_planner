#!/bin/sh
set -e
# Read the nameserver Docker injected into this container.
# On Docker Desktop (macOS/Windows) the embedded DNS may not be 127.0.0.11,
# so we detect it dynamically instead of hardcoding the address.
NGINX_RESOLVER=$(awk '/^nameserver/ { print $2; exit }' /etc/resolv.conf)
export NGINX_RESOLVER
exec /docker-entrypoint.sh "$@"
