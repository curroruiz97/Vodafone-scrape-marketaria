"""
Configuración central del scraper de Mi Vodafone Business.
Lee las variables del archivo .env (ver .env.example) y centraliza
los selectores de la web para que sean fáciles de ajustar si Vodafone
cambia el diseño.
"""
import os
from dotenv import load_dotenv

# Carga el .env que está junto a este archivo (funcione desde donde se ejecute)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ---------------------------------------------------------------------------
# URL de login
# ---------------------------------------------------------------------------
LOGIN_URL = os.getenv(
    "LOGIN_URL",
    "https://mvb.dxl.local.vodafone.es/mves/login?deepLinkEDC=%2FconsumoClarify",
)

# ---------------------------------------------------------------------------
# Credenciales de Mi Vodafone Business
# ---------------------------------------------------------------------------
VODAFONE_USER = os.getenv("VODAFONE_USER", "")
VODAFONE_PASS = os.getenv("VODAFONE_PASS", "")

# ---------------------------------------------------------------------------
# Buzón IONOS que recibe el código de verificación (2FA)
# ---------------------------------------------------------------------------
IMAP_HOST = os.getenv("IMAP_HOST", "imap.ionos.es")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")
# Filtro opcional del remitente del correo de Vodafone (si lo conoces).
OTP_SENDER = os.getenv("OTP_SENDER", "")
# Regex para extraer el código. Por defecto: una secuencia de 4 a 8 dígitos.
OTP_REGEX = os.getenv("OTP_REGEX", r"\b(\d{6})\b")
# Tiempo máximo (segundos) esperando a que llegue el correo con el código.
OTP_TIMEOUT = int(os.getenv("OTP_TIMEOUT", "120"))
# Segundos de espera inicial antes de la primera consulta (el correo tarda unos segundos).
OTP_INITIAL_WAIT = int(os.getenv("OTP_INITIAL_WAIT", "6"))
# Segundos entre reintentos de consulta del buzón.
OTP_POLL_INTERVAL = int(os.getenv("OTP_POLL_INTERVAL", "5"))

# Segundos de espera tras desplegar el listado, para que carguen las lineas.
LISTADO_WAIT = int(os.getenv("LISTADO_WAIT", "12"))

# ---------------------------------------------------------------------------
# Datos de la cuenta a consultar (valores fijos del flujo)
# ---------------------------------------------------------------------------
TARGET_CIF = os.getenv("TARGET_CIF", "B47573944")
TARGET_ACCOUNT = os.getenv("TARGET_ACCOUNT", "29250841")

# ---------------------------------------------------------------------------
# Supabase (proyecto "vodafone scrape")
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# ---------------------------------------------------------------------------
# Opciones de ejecución
# ---------------------------------------------------------------------------
# HEADLESS=false abre el navegador visible (útil para depurar la primera vez).
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("1", "true", "yes", "si", "sí")
# Reutilizar la sesión guardada para intentar saltar el 2FA en ejecuciones siguientes.
USE_SAVED_SESSION = os.getenv("USE_SAVED_SESSION", "true").lower() in ("1", "true", "yes", "si", "sí")

# ---------------------------------------------------------------------------
# Rutas internas
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, "session_state.json")
DEBUG_DIR = os.path.join(BASE_DIR, "debug")

# ---------------------------------------------------------------------------
# SELECTORES de la web.
# Cada entrada es una LISTA de candidatos: el scraper prueba uno por uno y usa
# el primero que encuentre visible. Así, si un selector falla, basta con
# añadir/ajustar uno aquí sin tocar el resto del código.
# NOTA: son la mejor estimación a partir de las capturas; es muy probable que
# haya que afinar 1-2 en la primera ejecución (el script guarda capturas y el
# HTML de la página en /debug cuando algo no cuadra, para poder corregirlos).
# ---------------------------------------------------------------------------
SELECTORS = {
    # --- Banner de cookies (aparece al entrar) ---
    "cookies_accept": [
        "button:has-text('Aceptar todas')",
        "text=Aceptar todas",
    ],

    # --- Login ---
    "user_input": [
        "input[name='username']",
        "input[id*='user' i]",
        "input[placeholder='Tu usuario']",
        "input[type='text']",
    ],
    "pass_input": [
        "input[name='password']",
        "input[id*='pass' i]",
        "input[placeholder='Contraseña']",
        "input[type='password']",
    ],
    "login_button": [
        "button:has-text('Acceder')",
        "input[type='submit']",
        "button[type='submit']",
    ],

    # --- 2FA: elegir método (email) y confirmar ---
    "otp_method_email_label": [
        "label:has-text('@')",
        "text=/@.*\\./",
    ],
    "otp_method_radios": ["input[type='radio']"],
    "otp_continue_button": [
        "button:has-text('Continuar')",
        "button[type='submit']",
    ],
    "otp_code_input": [
        "input[maxlength='6']",
        "input.mva10-c-text-field__input",
        "input[aria-labelledby='idSpan']",
        "input[type='text']",
        "input[type='tel']",
    ],
    "otp_confirm_button": [
        "#ManualLoginComp_btn_submitCodeOtp",
        "button:has-text('Confirmar')",
        "button[type='submit']",
    ],

    # --- Selección de CIF ("Antes de empezar...") ---
    "cif_dropdown": [
        "div[role='combobox']",
        "input[role='combobox']",
        "select",
        "input",
    ],

    # --- Pantalla de consumo: cuenta + buscar ---
    "buscar_por_cuenta_radio": [
        "label:has-text('Buscar por cuenta')",
        "text=Buscar por cuenta",
    ],
    "cuenta_dropdown": [
        "div[role='combobox']:has-text('Cuenta')",
        "div:has-text('Seleccionar')[role='combobox']",
        "div[role='combobox']",
        "select",
    ],
    "buscar_button": [
        "button:has-text('Buscar')",
    ],

    # --- Resultados ---
    "resultado_texto": [
        "text=/Se han encontrado .* líneas/",
    ],
    "expandir_listado": [
        "text=Líneas de la cuenta",
    ],
    "scroll_container": [
        "[class*='scroll']",
        "div:has(> div:has-text('Consumido'))",
    ],
    "fila_linea": [
        "div:has-text('Consumido')",
    ],
    "periodo_texto": [
        "text=/Periodo de consumo/",
    ],
}
