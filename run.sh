#!/usr/bin/env bash
set -e

# Als de container binnen Home Assistant draait, staat er meestal een
# persistente /data map beschikbaar (add-on data-map). Zet de SQLite-databank
# en geuploade foto's daar neer zodat ze een herstart/update overleven.
if [ -d "/data" ]; then
    mkdir -p /data/db /data/uploads
    ln -sfn /data/db /app/data
    ln -sfn /data/uploads /app/static/uploads
fi

exec python3 app.py
