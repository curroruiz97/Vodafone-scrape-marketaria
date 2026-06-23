#!/usr/bin/env bash
# Lanzador para el cron: ejecuta el scraper con el entorno virtual.
cd "$(dirname "$0")"
exec ./venv/bin/python scraper.py
