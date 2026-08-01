#!/usr/bin/env bash
set -euo pipefail

APP_ROOT=${1:-/opt/mycodexai}
ENV_FILE=${2:-/etc/mycodexai/mycodexai.env}

fail() { echo "FAIL: $*" >&2; exit 1; }
test -d "$APP_ROOT" || fail "application directory not found: $APP_ROOT"
test -f "$ENV_FILE" || fail "environment file not found: $ENV_FILE"
test -f "$APP_ROOT/deploy/mycodexai.service" || fail "systemd unit is missing"
test -f "$APP_ROOT/deploy/Caddyfile" || fail "Caddyfile is missing"
grep -q '^ENVIRONMENT=production$' "$ENV_FILE" || fail "ENVIRONMENT must be production"
grep -q '^SANDBOX_MODE=docker$' "$ENV_FILE" || fail "SANDBOX_MODE must be docker"
grep -q '^BROWSER_QA_ENABLED=false$' "$ENV_FILE" || fail "BROWSER_QA_ENABLED must be false"
grep -q '^AUTH_COOKIE_SECURE=true$' "$ENV_FILE" || fail "AUTH_COOKIE_SECURE must be true"
grep -q '^AUTH_REQUIRE_MFA_FOR_ADMIN=true$' "$ENV_FILE" || fail "administrator MFA must be required"
grep -q '^PUBLIC_ORIGIN=https://' "$ENV_FILE" || fail "PUBLIC_ORIGIN must use HTTPS"
command -v docker >/dev/null || fail "Docker is not installed"
command -v caddy >/dev/null || fail "Caddy is not installed"
command -v ollama >/dev/null || fail "Ollama is not installed"
docker image inspect mycodexai-sandbox:latest >/dev/null || fail "sandbox image is not built"
echo "PASS: production settings and required binaries are ready for MyCodexAI."
