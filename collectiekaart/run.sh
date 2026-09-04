#!/usr/bin/env bash
set -e

# Binnen Home Assistant is /data de map die een herstart en een update
# overleeft. De databank en de kaftfoto's horen daar thuis. Draait de
# container los, dan blijft alles gewoon in de projectmap staan.
if [ -d "/data" ]; then
    mkdir -p /data/db /data/uploads
    export COLLECTIEKAART_DATA_DIR=/data/db
    export COLLECTIEKAART_UPLOAD_DIR=/data/uploads
fi

exec python3 app.py
