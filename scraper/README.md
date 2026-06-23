# Scraper de consumo — Mi Vodafone Business → Supabase

Lee cada día el consumo de datos de todas las líneas de la cuenta y lo guarda
en Supabase (un snapshot por línea y día).

## Qué hace (resumen del flujo)

Login → elige el código de verificación **por email** → lee el código del buzón
IONOS por IMAP → confirma → selecciona CIF **B47573944** → cuenta **29250841** →
Buscar → despliega el listado → hace scroll hasta cargar todas las líneas →
extrae número + consumo + periodo → guarda en Supabase.

---

## 1. Instalación (una sola vez)

Necesitas **Python 3.11 o superior** instalado ([python.org](https://www.python.org/downloads/),
marca *"Add Python to PATH"* al instalar).

Abre una terminal (PowerShell) **en esta carpeta** y ejecuta:

```powershell
pip install -r requirements.txt
playwright install chromium
```

## 2. Configuración

1. Copia `.env.example` y renómbralo a `.env`.
2. Rellena tus valores reales:
   - `VODAFONE_USER` / `VODAFONE_PASS`: tus credenciales de Mi Vodafone Business.
   - `IMAP_USER` / `IMAP_PASS`: el buzón `jeremy@avenuemedia.io` y su contraseña
     (asegúrate de que **IMAP está activado** en IONOS).
   - `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`: del proyecto *vodafone scrape*
     (Supabase → Settings → API → *Project URL* y *service_role*).

> El `.env` contiene contraseñas: no lo subas a ningún sitio público.

## 3. Primera ejecución (en modo visible, para comprobar)

```powershell
python scraper.py --headful
```

Esto abre el navegador para que veas el proceso. Si todo va bien, al final dirá
`[7] Guardados N consumos en Supabase` y `[FIN] Estado: ok`.

**Si falla localizando algún elemento**, se guardará una captura y el HTML de la
página en la carpeta `debug/`. Pásame esos archivos y ajusto los selectores en
`config.py` (es el típico retoque de la primera vez).

## 4. Ejecución normal

```powershell
python scraper.py
```

Usa el modo invisible (`HEADLESS=true` en el `.env`). Puedes lanzarlo con el
archivo `run.bat` incluido (doble clic).

## 5. Programar todos los días (Programador de tareas de Windows)

1. Abre **Programador de tareas** → *Crear tarea básica*.
2. Nombre: `Scraper Vodafone`.
3. Desencadenador: **Diariamente**, elige una hora a la que el PC suela estar
   encendido (p. ej. 09:00).
4. Acción: **Iniciar un programa** → en *Programa o script* pon la ruta a
   `run.bat` (botón *Examinar* y selecciónalo).
5. En *Iniciar en (opcional)* pon la ruta de esta carpeta.
6. Finalizar. (Opcional: en las propiedades de la tarea, marca *Ejecutar tanto
   si el usuario inició sesión como si no* y *Ejecutar con los privilegios más
   altos*.)

> Requisito: el PC debe estar **encendido y sin suspensión** a esa hora.
> Si más adelante quieres que corra solo sin tener el PC encendido, se puede
> mover a la nube (GitHub Actions u Oracle Always Free, ambos gratis).

---

## Archivos

| Archivo | Para qué |
|---|---|
| `scraper.py` | Programa principal (flujo completo). |
| `config.py` | Configuración y **selectores** de la web (se ajustan aquí). |
| `otp_imap.py` | Lee el código 2FA del buzón IONOS por IMAP. |
| `db.py` | Guarda en Supabase (upserts + registro de ejecuciones). |
| `parse.py` | Normaliza el consumo a MB y las fechas del periodo. |
| `.env` | Tus credenciales (lo creas tú a partir de `.env.example`). |
| `debug/` | Capturas y HTML cuando algo falla (para depurar). |

## Notas

- **Idempotente**: si se ejecuta dos veces el mismo día, no duplica; actualiza
  el snapshot de ese día (restricción `unique(linea_id, fecha_captura)`).
- **Sesión**: guarda `session_state.json` para intentar saltar el 2FA en
  ejecuciones siguientes. Si Vodafone vuelve a pedir el código, lo lee igual.
- **Monitorización**: cada ejecución deja una fila en la tabla `scrape_runs`
  (estado ok/parcial/error, nº de líneas, mensaje de error).
