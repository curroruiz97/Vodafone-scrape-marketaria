# Ejecutar el scraper en GitHub Actions (cron diario, gratis)

GitHub ejecutara el scraper una vez al dia en la nube. No hace falta PC ni VPS.

## Estructura del repositorio

Sube al repo la carpeta del proyecto tal cual. Debe quedar asi:

```
tu-repo/
├── .github/workflows/scraper.yml   <- el workflow (ya creado)
├── .gitignore                       <- ya creado (NO sube .env ni datos)
└── scraper/
    ├── scraper.py, config.py, db.py, otp_imap.py, parse.py
    ├── requirements.txt
    └── ...
```

> El archivo `scraper/.env` con tus contraseñas **NO se sube** (esta en .gitignore).
> En GitHub, esos valores se ponen como **Secrets** (ver mas abajo).

## 1. Subir el codigo a GitHub

Desde tu PC (PowerShell), en la carpeta `software vodafone scrape`:

```powershell
git init
git add .
git commit -m "Scraper Vodafone + GitHub Actions"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

Antes de hacer push, comprueba que el `.env` NO aparece:
```powershell
git status        # no debe listar scraper/.env
```

## 2. Crear los Secrets

En tu repo de GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
Crea estos 6 (el nombre debe ser exacto):

| Nombre del secret | Valor (lo tienes en tu scraper/.env) |
|---|---|
| `VODAFONE_USER` | tu usuario de Mi Vodafone Business |
| `VODAFONE_PASS` | tu contraseña de Vodafone |
| `IMAP_USER` | jeremy@avenuemedia.io |
| `IMAP_PASS` | la contraseña del buzón IONOS |
| `SUPABASE_URL` | https://....supabase.co |
| `SUPABASE_SERVICE_ROLE_KEY` | la clave service_role de Supabase |

(El CIF, la cuenta, el host IMAP y el remitente ya van puestos en el propio workflow,
no son secretos.)

## 3. Probar a mano

Ve a la pestaña **Actions** del repo → workflow **"Scraper Vodafone diario"** →
botón **Run workflow**. Mira el registro en vivo: deberia hacer login, leer el código,
cargar las líneas y acabar guardando en Supabase. Comprueba la tabla `consumo_diario`.

## 4. Programado

Ya esta: el `cron` del workflow lo lanza cada día a las **06:00 UTC** (07:00/08:00 en
España). Para cambiar la hora, edita la línea `- cron: "0 6 * * *"`.

---

## Si falla (reCAPTCHA / IP de datacenter)

Las IPs de GitHub son de centro de datos; es posible que Vodafone muestre un reCAPTCHA
o bloquee. Para verlo:

1. En **Actions**, abre la ejecución que falló.
2. Descarga el artefacto **debug-...** (abajo, en "Artifacts").
3. Dentro está la captura `.png` y el `last_run.log`. Mándamelos y lo miramos.

Si la IP de GitHub diera problemas, el **VPS de IONOS** (IP española) sigue siendo el
plan B más fiable; el mismo código vale, solo cambia dónde se ejecuta.

## Notas

- Repo **privado**: el plan gratis da 2000 min/mes; una ejecución diaria (~5-8 min) cabe de sobra.
- GitHub pausa los cron si el repo lleva **60 días sin actividad**; con commits o ejecuciones manuales de vez en cuando se mantiene activo.
