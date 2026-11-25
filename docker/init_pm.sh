#!/bin/sh
set -e

# Dataset dirs are often Docker volume mounts (see docker-compose.yml). Ensure they exist
# and are writable by PHP-FPM (www-data, UID 82 on php:*-fpm-alpine).
DATA_UPLOADS="/var/www/html/bailenua/home/data/uploads"
DATA_ARTIFACTS="/var/www/html/bailenua/home/data/artifacts"

for d in "$DATA_UPLOADS" "$DATA_ARTIFACTS"; do
  mkdir -p "$d"
done

if id www-data >/dev/null 2>&1; then
  chown -R www-data:www-data "$DATA_UPLOADS" "$DATA_ARTIFACTS" 2>/dev/null || true
fi

# External data root (bind mount at e.g. /bailenua_data when BAILENUA_DATA_ROOT is set).
# Without chown, host-owned trees are not writable by PHP-FPM → SG-1 / uploads fail.
if [ -n "$BAILENUA_DATA_ROOT" ] && [ -d "$BAILENUA_DATA_ROOT" ]; then
  mkdir -p "$BAILENUA_DATA_ROOT/uploads" \
    "$BAILENUA_DATA_ROOT/artifacts" \
    "$BAILENUA_DATA_ROOT/sg1/scenarios" \
    "$BAILENUA_DATA_ROOT/sg1/generated" \
    "$BAILENUA_DATA_ROOT/sg1/logs" \
    "$BAILENUA_DATA_ROOT/sg1/tmp" \
    "$BAILENUA_DATA_ROOT/sg1/jobs" \
    "$BAILENUA_DATA_ROOT/sg1/data/weather"
  if id www-data >/dev/null 2>&1; then
    chown -R www-data:www-data \
      "$BAILENUA_DATA_ROOT/uploads" \
      "$BAILENUA_DATA_ROOT/artifacts" \
      "$BAILENUA_DATA_ROOT/sg1" \
      2>/dev/null || true
  fi
fi

exit 0
