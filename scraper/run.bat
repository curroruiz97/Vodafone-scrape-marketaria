@echo off
REM Lanza el scraper desde su propia carpeta (para el Programador de tareas)
cd /d "%~dp0"
python scraper.py
