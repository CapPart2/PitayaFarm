#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-8080}"
export PITAYA_DATA_DIR="${PITAYA_DATA_DIR:-/app/data}"

if [[ -z "${ADMIN_TOKEN:-}" || -z "${DEFAULT_ADMIN_PASSWORD:-}" ]]; then
  echo "ADMIN_TOKEN and DEFAULT_ADMIN_PASSWORD must be set in Railway Variables."
  exit 1
fi

if [[ "$ADMIN_TOKEN" == "admin-secret-token-12345" || "$DEFAULT_ADMIN_PASSWORD" == "admin123" ]]; then
  echo "Use unique values for ADMIN_TOKEN and DEFAULT_ADMIN_PASSWORD."
  exit 1
fi

mkdir -p "$PITAYA_DATA_DIR/uploads"

# Legacy dashboard code still refers to these project-relative paths.  Point
# them at the persistent Railway volume without changing its public URLs.
ln -sfn "$PITAYA_DATA_DIR/uploads" /app/uploads
ln -sfn "$PITAYA_DATA_DIR/pitaya_database.db" /app/pitaya_database.db

envsubst '${PORT}' < /app/deploy/nginx.conf.template > /etc/nginx/sites-enabled/default

gunicorn app:app --bind 127.0.0.1:5000 --workers 1 --timeout 180 --access-logfile - --error-logfile - &
disease_pid=$!
gunicorn dashboard_api:app --bind 127.0.0.1:5001 --workers 1 --timeout 300 --access-logfile - --error-logfile - &
dashboard_pid=$!
nginx -g 'daemon off;' &
nginx_pid=$!

cleanup() {
  kill "$disease_pid" "$dashboard_pid" "$nginx_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait -n "$disease_pid" "$dashboard_pid" "$nginx_pid"
