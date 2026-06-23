# Plan: Scraper diario de consumo de datos — Mi Vodafone Business → Supabase

**Cuenta objetivo:** MARKETARIA SL — CIF **B47573944**, cuenta **29250841** (~102 líneas)
**Objetivo:** Cada 24 h, leer todas las líneas con su consumo de datos del periodo en curso y guardar un histórico en Supabase.
**Login:** usuario + contraseña **+ código de verificación por email (2FA)** enviado a `jeremy@avenuemedia.io` (buzón **IONOS**, leíble por IMAP).
**Acceso web:** la URL de login es pública (se abre desde cualquier sitio) → apta para alojar en la nube.

---

## 1. Resumen de la solución

Un proceso automático que, una vez al día y **sin intervención**:

1. Abre un navegador headless (Playwright/Chromium) y entra en la URL de login.
2. Mete usuario + contraseña y pulsa **Acceder**.
3. Elige recibir el código de verificación **por email** (2ª opción).
4. Se conecta por **IMAP al buzón de IONOS**, localiza el correo nuevo de Vodafone, extrae el código y lo introduce → **Confirmar**.
5. Selecciona el CIF **B47573944**.
6. Selecciona la cuenta **29250841** y pulsa **Buscar**.
7. Despliega el listado (icono de flecha roja) y hace **scroll incremental** dentro del recuadro hasta que cargan las **102 líneas**.
8. Extrae por cada línea: número + consumo de datos + periodo ("1 Jun – 18 Jun").
9. Normaliza los valores (ej. "0 MB", "1,2 GB" → MB) y guarda un **snapshot diario** en Supabase (sin duplicar si se repite el día).
10. Registra el resultado de la ejecución y avisa si algo falla.

El punto clave técnico: el consumo se carga por JavaScript tras el login, así que hace falta un navegador real (Playwright); y el 2FA por email se resuelve leyendo el buzón por IMAP, lo que permite que todo corra solo.

---

## 2. Flujo diario EXACTO (lo que hará el script cada día)

| Paso | Acción | Valor fijo |
|---|---|---|
| 1 | Ir a la URL de login e introducir credenciales → **Acceder** | `https://mvb.dxl.local.vodafone.es/mves/login?deepLinkEDC=%2FconsumoClarify` |
| 2 | Elegir método de envío del código → **2ª opción (email)** | email (`j*****@m*****.es`) |
| 3 | Leer el código del buzón IONOS por IMAP, pegarlo → **Confirmar** | buzón `jeremy@avenuemedia.io` |
| 4 | Seleccionar CIF | **B47573944** |
| 5 | Seleccionar cuenta + **Buscar** | **29250841** |
| 6 | Desplegar listado (flecha roja) y **scroll** hasta cargar todas | hasta ver las 102 líneas |
| 7 | Extraer y guardar en Supabase | snapshot del día |

> **Importante (matización a tu nota sobre "solo las líneas nuevas"):** los pasos 1–6 se ejecutan **cada día** (cada ejecución es una sesión nueva), pero siempre con los mismos valores fijos, así que no hay nada que decidir. Y en el paso 7 hay que **re-leer las 102 líneas todos los días**, no solo las nuevas: el objetivo es registrar el consumo de *cada* línea *cada* día (el consumo cambia a diario). Lo de "detectar las nuevas" aplica solo al **maestro de líneas**: si aparece un número de teléfono que no existía, se da de alta automáticamente; pero el snapshot de consumo es siempre de todas. Resumen: full scan diario de las 102 + alta automática de líneas nuevas.

---

## 3. Hosting — DECISIÓN: empezar en tu PC (€0)

Decidido: **ejecutar el scraper en tu propio PC** con el Programador de tareas de Windows. Coste 0 € e ideal para depurar. Único requisito: el equipo debe estar **encendido y sin suspensión** a la hora programada (elegir una hora en la que sueles tenerlo abierto).

Un VPS no es más que un ordenador en la nube encendido 24/7; aquí solo serviría para no depender de que tu PC esté abierto. No hace falta para empezar.

Si más adelante quieres que corra solo sin tener el PC encendido, hay opciones **gratis**:

| Opción | Coste | Cuándo usarla |
|---|---|---|
| **Tu PC (Programador de tareas)** — elegida | 0 € | Ahora. Simple e ideal para depurar. Requiere PC encendido a la hora. |
| GitHub Actions (cron en la nube) | 0 € | Si quieres nube sin PC. A vigilar: IP de datacenter (posible bloqueo de Vodafone; hay que probar). |
| Oracle Cloud "Always Free" (VM gratis indefinida) | 0 € | Servidor real 24/7 gratis; algo más de configuración. |
| VPS de pago (Hetzner, OVH, IONOS…) | ~3–6 €/mes | Solo si quieres máxima fiabilidad sin complicaciones. |

---

## 4. Stack tecnológico

- **Python 3.11+**
- **Playwright** (Chromium headless) para el navegador.
- **imap-tools / imaplib** para leer el código de IONOS por IMAP.
- **supabase-py** (o REST) para escribir en Supabase.
- **python-dotenv** para credenciales (`.env`).
- **cron** (VPS) o Programador de tareas (Windows).
- **Docker** opcional en la VPS para empaquetar navegador + dependencias.

---

## 5. Lectura del código 2FA por IMAP (IONOS)

- **Servidor IMAP IONOS:** `imap.ionos.es` (o `imap.ionos.com`), **puerto 993, SSL/TLS**.
- **Autenticación:** dirección completa `jeremy@avenuemedia.io` + contraseña del buzón. (IONOS usa la propia contraseña del correo; hay que tener **IMAP activado** en el buzón, que suele estarlo por defecto.)
- **Lógica de extracción:**
  1. Anotar la hora justo antes de pedir el código.
  2. Conectar por IMAP y buscar en INBOX correos **de Vodafone** recibidos **después** de esa hora (para no coger un código viejo).
  3. Reintentar cada pocos segundos (el correo tarda unos segundos en llegar), hasta ~60 s.
  4. Extraer el código (regex sobre el cuerpo/asunto, p. ej. el número de 6 dígitos).
  5. Leer en modo no destructivo (`BODY.PEEK`, sin borrar ni alterar el resto del buzón). Solo se tocan los correos de OTP de Vodafone.
- **Validez del código:** 10 min. Si caduca o falla, usar "Reenviar código" y reintentar una vez.

---

## 6. Esquema de base de datos en Supabase

```sql
-- Maestro de líneas (una fila por número)
create table if not exists lineas (
  id                bigint generated always as identity primary key,
  numero_linea      text not null unique,
  cif               text,            -- "B47573944"
  cuenta            text,            -- "29250841"
  alias             text,
  activa            boolean default true,
  primera_vez_vista timestamptz default now(),
  ultima_vez_vista  timestamptz default now()
);

-- Histórico: un snapshot por línea y día
create table if not exists consumos (
  id             bigint generated always as identity primary key,
  linea_id       bigint not null references lineas(id) on delete cascade,
  fecha_captura  date not null default current_date,
  periodo_inicio date,
  periodo_fin    date,
  consumo_mb     numeric,           -- normalizado a MB
  consumo_texto  text,              -- crudo: "Consumido 0 MB de tus datos ilimitados"
  tipo_plan      text,              -- ej. "ilimitado"
  capturado_en   timestamptz default now(),
  unique (linea_id, fecha_captura)  -- 1 registro por línea/día (idempotencia)
);

-- Registro de cada ejecución (monitorización)
create table if not exists scrape_runs (
  id                 bigint generated always as identity primary key,
  iniciado_en        timestamptz default now(),
  finalizado_en      timestamptz,
  estado             text,          -- 'ok' | 'parcial' | 'error'
  lineas_detectadas  int,
  lineas_guardadas   int,
  mensaje_error      text
);

create index if not exists idx_consumos_linea_fecha on consumos (linea_id, fecha_captura);
create index if not exists idx_consumos_fecha       on consumos (fecha_captura);
```

- `unique (linea_id, fecha_captura)` → **upsert** idempotente (si corre dos veces el mismo día, actualiza, no duplica).
- Se guarda el valor normalizado (`consumo_mb`) y el texto crudo (`consumo_texto`).
- `scrape_runs` te dice qué días corrió bien y cuántas líneas capturó (deberían ser ~102).
- **RLS:** activado, sin políticas públicas; solo escribe el scraper con la `service_role key`.

---

## 7. Normalización de datos

`"Consumido 0 MB de tus datos ilimitados"` →
- `consumo_mb` = 0 (convirtiendo GB→MB y tratando la coma decimal: "1,2 GB" → 1228.8 MB).
- `tipo_plan` = "ilimitado".
- `consumo_texto` = texto original. Si no se puede parsear: `consumo_mb = null` y se conserva el texto.

---

## 8. Programación cada 24 h

- **VPS (cron):** p. ej. `0 6 * * *` (06:00) para tener el día anterior cerrado y evitar horas punta.
- **PC (Windows):** Programador de tareas, disparador diario.
- Cada ejecución registra en log y en `scrape_runs`; idempotente por la restricción única.

---

## 9. Seguridad y credenciales

- En `.env` (nunca en código ni en Git; `.env` en `.gitignore`):
  - Usuario y contraseña de Vodafone.
  - `jeremy@avenuemedia.io` + contraseña IMAP del buzón IONOS.
  - URL + `service_role key` de Supabase.
- La contraseña del buzón es sensible (es un correo de persona): guardarla cifrada/restringida (`chmod 600` en VPS) y leer el buzón en modo no destructivo.
- Supabase: `service_role` solo en servidor; RLS activo sin políticas abiertas.

---

## 10. Robustez y monitorización

- **Reintentos** con espera ante fallos de red/carga (login, OTP, scroll).
- **Esperas explícitas** de Playwright (no `sleep` fijos).
- **Capturas de pantalla** al fallar, para depurar.
- **Logging** a archivo con fecha + filas en `scrape_runs`.
- **Validación:** comprobar que nº de líneas guardadas ≈ las anunciadas ("Se han encontrado 102 líneas"). Si difiere mucho → estado `parcial` + aviso.
- **Alertas** si falla: email, Telegram, o registro `estado='error'` revisable.
- **Detección de cambios en la web:** si Vodafone cambia el diseño, fallan los selectores → el aviso lo detecta y se ajustan en el archivo de config (los selectores van aislados en un solo sitio).

---

## 11. Consideraciones anti-bot y legales

- Es tu propia cuenta y tus propios datos → uso legítimo.
- Buenas prácticas: 1 ejecución/día, user-agent realista, scroll a ritmo humano, reutilizar sesión cuando se pueda.
- Hay reCAPTCHA en la página de login: normalmente es invisible/score-based y no molesta a un navegador real headful/headless bien configurado; si en algún momento exige interacción, se gestiona con sesión persistente o ajustes. (Lo validamos en la Fase 2.)

---

## 12. Plan de implementación por fases

**Fase 0 — Preparación**
- Credenciales Vodafone + contraseña IMAP del buzón IONOS + claves Supabase.

**Fase 1 — Base de datos**
- Crear las 3 tablas e índices en Supabase (SQL de la sección 6).

**Fase 2 — Login + 2FA (en tu PC)**
- Login automatizado, elegir email, leer código por IMAP, confirmar.
- Validar que el reCAPTCHA no bloquea.

**Fase 3 — Navegación + extracción**
- CIF B47573944 → cuenta 29250841 → Buscar → desplegar → scroll hasta cargar las 102 → extraer + normalizar.

**Fase 4 — Integración Supabase**
- Upserts en `lineas`/`consumos` + `scrape_runs`. Validar idempotencia (2 veces el mismo día sin duplicar).

**Fase 5 — Programación**
- Probar 2–3 días en local → mover a VPS + cron.

**Fase 6 — Monitorización**
- Alertas de fallo + revisión de `scrape_runs`. (Opcional) panel de evolución del consumo.

---

## 13. Qué necesito de ti para empezar

1. **Usuario y contraseña** de Mi Vodafone Business.
2. **Contraseña IMAP** del buzón `jeremy@avenuemedia.io` (IONOS) — y confirmar que IMAP está activado.
3. **URL del proyecto Supabase + `service_role key`** (o acceso para crear el esquema).
4. **Hosting final:** ¿empezamos en tu PC y luego VPS, o vamos directos a VPS?
5. (Opcional) Canal de **alertas**: email, Telegram o solo registro en BD.

---

## 14. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Vodafone cambia el diseño | Deja de leer | Selectores aislados + alertas |
| reCAPTCHA exige interacción | Login falla | Sesión persistente / navegador bien configurado; revisar en Fase 2 |
| El correo OTP tarda o no llega | Login falla | Polling IMAP ~60s + "Reenviar código" + reintento |
| Cambio de contraseña del buzón/Vodafone | Login falla | Centralizado en `.env`; alerta clara para actualizar |
| La lista no carga las 102 | Datos incompletos | Validación nº líneas + estado 'parcial' + reintento |
| Caída de VPS/PC | Se pierde un día | `scrape_runs` lo detecta; relanzar (histórico por fecha) |

---

## 15. Coste estimado

- **Supabase:** plan gratuito de sobra (~37.000 filas/año).
- **VPS:** ~3–6 €/mes (o 0 € en tu PC).
- **Mantenimiento:** mínimo, salvo cambios en la web de Vodafone.
