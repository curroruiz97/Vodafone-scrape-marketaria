# Desplegar el scraper en el VPS de IONOS (Ubuntu 22.04)

El scraper ya funciona en tu PC. Estos pasos lo dejan corriendo solo, cada dia,
en tu VPS de IONOS (con Plesk no pasa nada: usamos SSH + cron por debajo).

Necesitas: la **IP del VPS** y la **contrasena de root** (las tienes en el panel de IONOS).

---

## 1. Subir la carpeta del scraper al VPS

Desde tu PC (PowerShell), sube la carpeta `scraper` completa:

```powershell
scp -r "C:\Users\fruiz\Desktop\software vodafone scrape\scraper" root@LA_IP_DEL_VPS:/opt/
```

Quedara en `/opt/scraper`. (Alternativa con interfaz grafica: programa **WinSCP**,
arrastrando la carpeta `scraper` dentro de `/opt`.)

> Incluye tu `.env` con las credenciales (va dentro de la carpeta). 

---

## 2. Conectarte por SSH e instalar

```powershell
ssh root@LA_IP_DEL_VPS
```

Ya dentro del VPS:

```bash
cd /opt/scraper

# (opcional) empezar limpio: borrar sesion/depuracion copiadas del PC
rm -f session_state.json
rm -rf debug

# proteger el archivo de credenciales
chmod 600 .env

# instalar todo (Python, librerias, Chromium). Tarda unos minutos.
bash install_vps.sh
```

---

## 3. Probar a mano (una vez)

```bash
cd /opt/scraper
./venv/bin/python scraper.py
```

Debe terminar en `[7] Guardados N consumos` y `[FIN] Estado: ok`.
Comprueba en Supabase que la tabla `consumo_diario` tiene las filas de hoy.

Si algo falla, mira el log y la captura:
```bash
cat /opt/scraper/last_run.log
ls /opt/scraper/debug
```

---

## 4. Programar la ejecucion diaria (cron)

```bash
crontab -e
```

Anade esta linea al final (ejecuta cada dia a las 07:00, hora de Madrid):

```
0 7 * * * /opt/scraper/run_vps.sh >> /opt/scraper/cron.log 2>&1
```

Guarda y cierra. Listo: cada dia a las 7:00 se ejecutara solo.

---

## 5. Comprobar que va funcionando

- Log de la ultima ejecucion:  `cat /opt/scraper/last_run.log`
- Salida acumulada del cron:    `tail -n 50 /opt/scraper/cron.log`
- En Supabase: la tabla `consumo_diario` debe ganar ~97 filas nuevas cada dia,
  y `scrape_runs` muestra el estado de cada ejecucion (ok / parcial / error).

---

## Notas

- **reCAPTCHA**: si Vodafone bloqueara la IP del VPS (poco probable siendo IONOS
  espanol, pero posible), se vera en `last_run.log` / `debug/`. Si pasa, me dices
  y buscamos alternativa.
- **Cambiar la hora**: edita el `0 7 * * *` del cron (minuto hora * * *).
- **Actualizar el codigo**: si cambiamos algo, vuelve a subir los archivos con scp
  (paso 1) y ya esta; no hace falta reinstalar salvo que cambien las librerias.
