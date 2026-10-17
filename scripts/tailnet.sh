#!/usr/bin/env bash
# Run ENTRACCESS UK Collector on this machine and publish it with Tailscale Funnel.
#
#   scripts/tailnet.sh          start (or update) and publish
#   scripts/tailnet.sh stop     stop publishing and stop the containers
#
# The public address is https://<this machine>.<tailnet>.ts.net:10000. It is
# reachable only while this machine is on and running Tailscale, so it is for
# demos and pilots, not production. Demo data only: never load real children.
set -euo pipefail
cd "$(dirname "$0")/.."

FUNNEL_PORT="${FUNNEL_PORT:-10000}"   # Funnel allows 443, 8443 or 10000
TS=(tailscale)
[[ -n "${TS_SOCKET:-}" ]] && TS+=(--socket="$TS_SOCKET")
COMPOSE=(docker compose --env-file .env.tailnet -f docker-compose.yml -f docker-compose.tailnet.yml)

if [[ "${1:-}" == "stop" ]]; then
  "${TS[@]}" funnel --https="$FUNNEL_PORT" off || true
  "${COMPOSE[@]}" down
  exit 0
fi

host=$("${TS[@]}" status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
url="https://${host}:${FUNNEL_PORT}"

if [[ ! -f .env.tailnet ]]; then
  rand() { python3 -c 'import secrets; print(secrets.token_urlsafe(48))'; }
  cat > .env.tailnet <<ENV
# Written by scripts/tailnet.sh. Keep it out of git.
TAILNET_URL=${url}
SECRET_KEY=$(rand)
PASS_SIGNING_KEY=$(rand)
ENV
  chmod 600 .env.tailnet
fi

# Added separately so an existing .env.tailnet gains it too.
if ! grep -q '^TAILNET_MAIL_PASSWORD=' .env.tailnet; then
  echo "TAILNET_MAIL_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(9))')" >> .env.tailnet
fi
mail_port=$(grep -E '^TAILNET_MAIL_PORT=' .env.tailnet | cut -d= -f2 || true)
mail_port="${mail_port:-8126}"

port=$(grep -E '^TAILNET_WEB_PORT=' .env.tailnet | cut -d= -f2 || true)
port="${port:-8190}"

"${COMPOSE[@]}" up -d --build
"${TS[@]}" funnel --bg --https="$FUNNEL_PORT" "http://127.0.0.1:${port}"
# The email viewer, at /mail on the same address, so it works on a phone.
"${TS[@]}" funnel --bg --https="$FUNNEL_PORT" --set-path=/mail "http://127.0.0.1:${mail_port}/mail"

echo
echo "Email viewer: ${url}/mail/  (user mail, password TAILNET_MAIL_PASSWORD in .env.tailnet)"
echo "ENTRACCESS UK Collector is live at ${url}"
echo "Demo data (first run): ${COMPOSE[*]} exec api python -m app.seed"
