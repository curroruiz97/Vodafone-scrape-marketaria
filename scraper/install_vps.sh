#!/usr/bin/env bash
# Instalacion del scraper en un VPS Ubuntu 22.04 (ejecutar como root: bash install_vps.sh)
set -e
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"
echo "== Carpeta de la app: $APP_DIR =="

echo "== 1/4 Dependencias del sistema =="
apt-get update
apt-get install -y python3 python3-venv python3-pip

echo "== 2/4 Entorno virtual + librerias Python =="
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "== 3/4 Chromium + dependencias de Playwright =="
./venv/bin/playwright install --with-deps chromium

echo "== 4/4 Zona horaria Europe/Madrid =="
timedatectl set-timezone Europe/Madrid || echo "(no se pudo cambiar la zona horaria; no es critico)"

echo ""
echo "Instalacion COMPLETADA."
echo "Prueba ahora:  cd \"$APP_DIR\" && ./venv/bin/python scraper.py"
