"""
Scraper de consumo de datos de Mi Vodafone Business.

Flujo diario:
  cookies -> login -> 2FA por email (IMAP) -> CIF -> Empezar -> cuenta -> Buscar
  -> desplegar listado -> esperar -> scroll incremental del recuadro
  -> extraer (numero + consumo + periodo) -> guardar en Supabase.

Uso:
  python scraper.py            # modo normal (headless segun .env)
  python scraper.py --headful  # abre el navegador visible (para depurar)
"""
import argparse
import os
import re
import sys
import time
import traceback
from datetime import datetime

from playwright.sync_api import sync_playwright

import config
import db
from otp_imap import fetch_otp_code, now_utc, get_baseline_uid
from parse import parse_consumo, parse_periodo


# ===========================================================================
# Helpers de Playwright
# ===========================================================================
def first_visible(page, candidates, timeout=6000):
    """Devuelve el primer selector candidato que este visible."""
    last_err = None
    per = max(1500, timeout // max(1, len(candidates)))
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=per)
            return loc
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"No se encontro ningun elemento de: {candidates} ({last_err})")


def try_click_text(page, texto, exact=False, timeout=4000):
    try:
        loc = page.get_by_text(texto, exact=exact).first
        loc.wait_for(state="visible", timeout=timeout)
        loc.click()
        return True
    except Exception:  # noqa: BLE001
        return False


def dump_debug(page, etiqueta):
    os.makedirs(config.DEBUG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(config.DEBUG_DIR, f"{ts}_{etiqueta}")
    try:
        page.screenshot(path=base + ".png", full_page=True)
    except Exception:  # noqa: BLE001
        pass
    try:
        with open(base + ".html", "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception:  # noqa: BLE001
        pass
    print(f"[DEBUG] Guardado {base}.png / .html")


# ===========================================================================
# Pasos del flujo
# ===========================================================================
def accept_cookies(page):
    """Acepta el banner de cookies si aparece (no falla si no esta)."""
    page.wait_for_timeout(1000)
    for sel in config.SELECTORS.get("cookies_accept", []):
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=4000)
            loc.click()
            print("[1] Cookies aceptadas.")
            page.wait_for_timeout(500)
            return
        except Exception:  # noqa: BLE001
            continue


def do_login(page):
    print("[1] Login...")
    page.goto(config.LOGIN_URL, wait_until="domcontentloaded")
    accept_cookies(page)
    first_visible(page, config.SELECTORS["user_input"]).fill(config.VODAFONE_USER)
    first_visible(page, config.SELECTORS["pass_input"]).fill(config.VODAFONE_PASS)
    page.wait_for_timeout(300)
    first_visible(page, config.SELECTORS["login_button"]).click()
    page.wait_for_timeout(2500)


def handle_2fa(page):
    """Si aparece la pantalla de verificacion, elige email, lee el codigo y confirma."""
    try:
        cont = first_visible(page, config.SELECTORS["otp_continue_button"], timeout=8000)
    except RuntimeError:
        print("[2] No se pidio 2FA (sesion recordada).")
        return

    print("[2] 2FA: eligiendo email...")
    elegido = try_click_text(page, re.compile(r"@.*\."))
    if not elegido:
        radios = page.locator(config.SELECTORS["otp_method_radios"][0])
        if radios.count() >= 2:
            radios.nth(1).check()

    baseline_uid = get_baseline_uid(
        config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USER, config.IMAP_PASS)
    desde = now_utc()
    cont.click()

    print("[3] Solicitado el codigo; esperando el correo NUEVO por IMAP...")
    code = fetch_otp_code(
        config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USER, config.IMAP_PASS,
        since_dt=desde, sender=config.OTP_SENDER, regex=config.OTP_REGEX,
        timeout=config.OTP_TIMEOUT,
        poll_interval=config.OTP_POLL_INTERVAL,
        initial_wait=config.OTP_INITIAL_WAIT,
        min_uid=baseline_uid,
    )
    print(f"[3] Codigo recibido: {code}")
    code_box = first_visible(page, config.SELECTORS["otp_code_input"], timeout=15000)
    code_box.click()
    try:
        code_box.fill("")
        code_box.press_sequentially(code, delay=80)
    except Exception:  # noqa: BLE001
        code_box.fill(code)
    page.wait_for_timeout(600)
    first_visible(page, config.SELECTORS["otp_confirm_button"]).click()
    page.wait_for_timeout(2500)


def select_cif(page):
    print(f"[4] Seleccionando CIF {config.TARGET_CIF}...")
    if not page.get_by_text(config.TARGET_CIF).count():
        try:
            first_visible(page, config.SELECTORS["cif_dropdown"], timeout=6000).click()
        except RuntimeError:
            print("[4] No aparecio el selector de CIF; continuo.")
            return
    if not try_click_text(page, config.TARGET_CIF, exact=True, timeout=6000):
        try:
            box = first_visible(page, config.SELECTORS["cif_dropdown"], timeout=3000)
            box.fill(config.TARGET_CIF)
            page.wait_for_timeout(500)
            try_click_text(page, config.TARGET_CIF, exact=True)
        except RuntimeError:
            pass
    try:
        first_visible(page, [
            "button:has-text('Empezar')",
            "button:has-text('Continuar')",
            "button:has-text('Aceptar')",
        ], timeout=8000).click()
        print("[4] Pulsado boton Empezar.")
    except RuntimeError:
        print("[4] No se encontro el boton Empezar.")
    page.wait_for_timeout(3000)


def dismiss_popup(page):
    """Cierra avisos emergentes (ej. 'Mejoras en Soporte Tecnico') si aparecen.
    No falla si no hay ninguno."""
    for sel in ("div[role='dialog'] button:has-text('Aceptar')",
                "button:has-text('Aceptar')"):
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=1500)
            loc.click()
            print("[5] Popup cerrado (Aceptar).")
            page.wait_for_timeout(800)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def select_account_and_search(page):
    acc = config.TARGET_ACCOUNT
    print(f"[5] Seleccionando cuenta {acc} y buscando...")

    dismiss_popup(page)
    try_click_text(page, "Buscar por cuenta", timeout=4000)
    page.wait_for_timeout(400)

    for sel in ("button:has(.vfes-dropdown__placeholder)",
                ".vfes-dropdown__placeholder",
                "button:has-text('Seleccionar')",
                "div[role='combobox']"):
        try:
            page.locator(sel).first.click(timeout=4000)
            print(f"[5] Desplegable de cuenta abierto ({sel}).")
            break
        except Exception:  # noqa: BLE001
            continue
    page.wait_for_timeout(1200)

    seleccionado = False
    for sel in (f"#combobox-list label[for='subcheckbox{acc}']",
                f"label[for='subcheckbox{acc}']",
                f"#combobox-list li:has-text('{acc}')",
                f"#combobox-list:has-text('{acc}')"):
        try:
            page.locator(sel).first.click(timeout=3000)
            seleccionado = True
            print(f"[5] Cuenta marcada ({sel}).")
            break
        except Exception:  # noqa: BLE001
            continue
    if not seleccionado:
        page.evaluate(
            """
            (acc) => {
              const lbl = document.querySelector('label[for="subcheckbox' + acc + '"]');
              const cb = document.getElementById('subcheckbox' + acc);
              if (lbl) { lbl.click(); }
              if (cb) {
                if (!cb.checked) { cb.click(); }
                cb.dispatchEvent(new Event('change', { bubbles: true }));
              }
            }
            """,
            acc,
        )
        print("[5] Cuenta marcada por JS (fallback).")
    page.wait_for_timeout(1000)

    btn = page.locator("button[name='Buscar'], button:has-text('Buscar')").first
    btn.wait_for(state="visible", timeout=8000)
    habilitado = False
    for _ in range(24):
        try:
            if btn.is_enabled():
                habilitado = True
                break
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(500)
    if not habilitado:
        raise RuntimeError("El boton Buscar sigue deshabilitado: la cuenta no se selecciono bien.")
    dismiss_popup(page)
    btn.click()
    print("[5] Pulsado Buscar.")


# JS que extrae las filas (numero + consumo) de forma robusta a cambios de clase.
_JS_EXTRACT = r"""
() => {
  const phoneRe = /\b([6789]\d{8})\b/;
  const consRe  = /Consumido[\s\S]*?(?:TB|GB|MB|KB|B)\b[^\n\r]*/i;
  const out = [];
  const seen = new Set();
  const els = document.querySelectorAll('div,li,article,section,tr');
  for (const el of els) {
    const t = el.innerText || '';
    if (t.length === 0 || t.length > 400) continue;
    if (!/Consumido/i.test(t)) continue;
    const pm = t.match(phoneRe);
    if (!pm) continue;
    const phone = pm[1];
    if (seen.has(phone)) continue;
    let childMatch = false;
    for (const c of el.children) {
      const ct = c.innerText || '';
      if (phoneRe.test(ct) && /Consumido/i.test(ct)) { childMatch = true; break; }
    }
    if (childMatch) continue;
    seen.add(phone);
    const cm = t.match(consRe);
    out.push({numero: phone, consumo: (cm ? cm[0] : t).trim()});
  }
  return out;
}
"""

# Scrollea SOLO el contenedor REALMENTE scrollable (overflow auto/scroll) que
# contiene las filas, y dispara el evento 'scroll' para forzar la carga del
# siguiente lote. Devuelve info para diagnostico (o {found:false}).
_JS_SCROLL = r"""
() => {
  let box = null, bestH = 0;
  for (const el of document.querySelectorAll('div,ul,section,tbody')) {
    if (el === document.body || el === document.documentElement) continue;
    const st = getComputedStyle(el);
    const oy = st.overflowY;
    const canScroll = (oy === 'auto' || oy === 'scroll' || oy === 'overlay');
    if (canScroll && el.scrollHeight > el.clientHeight + 10
        && /Consumido/i.test(el.innerText || '')) {
      if (el.scrollHeight > bestH) { bestH = el.scrollHeight; box = el; }
    }
  }
  if (!box) return { found: false };
  box.scrollTop = box.scrollHeight;
  box.dispatchEvent(new Event('scroll', { bubbles: true }));
  return { found: true, top: Math.round(box.scrollTop),
           sh: box.scrollHeight, ch: box.clientHeight };
}
"""

# Fallback: llevar la ultima fila cargada al fondo de su contenedor.
_JS_SCROLL_LASTROW = r"""
() => {
  const rows = [...document.querySelectorAll('div,li,tr')].filter(
    e => /Consumido/i.test(e.textContent || '') && e.children.length <= 5);
  if (rows.length) { rows[rows.length - 1].scrollIntoView({ block: 'end' }); return true; }
  return false;
}
"""


def _scroll_listado(page):
    """Scrollea el recuadro de lineas para cargar el siguiente lote."""
    info = None
    try:
        info = page.evaluate(_JS_SCROLL)
    except Exception:  # noqa: BLE001
        info = None
    if not info or not info.get("found"):
        try:
            page.evaluate(_JS_SCROLL_LASTROW)
        except Exception:  # noqa: BLE001
            pass
    return info


def expand_and_extract(page):
    print("[6] Esperando a que carguen los resultados...")
    page.wait_for_timeout(3000)
    dismiss_popup(page)

    total = None
    for _ in range(20):
        body = page.inner_text("body")
        m = re.search(r"encontrado\s+(\d+)\s+l[ií]neas", body, re.I)
        if m:
            total = int(m.group(1))
            print(f"[6] La web anuncia {total} lineas.")
            break
        page.wait_for_timeout(1000)

    print("[6] Desplegando listado...")
    try_click_text(page, "Líneas de la cuenta", timeout=8000)

    # Fase 1: esperar a que aparezca la primera linea SIN hacer scroll.
    print("[6] Esperando a que aparezcan las lineas (sin scroll)...")
    espera_max = time.time() + config.LISTADO_WAIT + 40
    while time.time() < espera_max:
        if len(page.evaluate(_JS_EXTRACT)) > 0:
            break
        page.wait_for_timeout(1500)

    periodo_ini = periodo_fin = None
    try:
        ptxt = page.get_by_text("Periodo de consumo").first.inner_text(timeout=4000)
        periodo_ini, periodo_fin = parse_periodo(ptxt)
    except Exception:  # noqa: BLE001
        pass

    # Fase 2: carga incremental. Scroll del recuadro -> esperar lote -> repetir.
    print("[6] Cargando todas las lineas (scroll incremental)...")
    deadline = time.time() + 300
    prev, estable = -1, 0
    filas = []
    while time.time() < deadline:
        filas = page.evaluate(_JS_EXTRACT)
        n = len(filas)
        if n != prev:
            print(f"    ...{n} lineas cargadas")
            prev = n
            estable = 0
        else:
            estable += 1

        if n > 0 and total is not None and n >= total:
            break
        if n > 0 and total is None and estable >= 6:
            break
        if total is not None and estable >= 15:
            print("[6] Aviso: el numero de lineas dejo de crecer antes de llegar al total.")
            break

        _scroll_listado(page)
        page.wait_for_timeout(1500)

    filas = page.evaluate(_JS_EXTRACT)
    print(f"[6] Extraidas {len(filas)} lineas.")
    if total is not None and len(filas) < total:
        dump_debug(page, "listado_parcial")
    return filas, total, periodo_ini, periodo_fin


# ===========================================================================
# Orquestacion
# ===========================================================================
def run(headful=False):
    headless = config.HEADLESS and not headful
    run_id = db.start_run()
    estado = "error"
    guardados = 0
    total = None
    error_msg = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx_args = dict(
            locale="es-ES",
            timezone_id="Europe/Madrid",
            viewport={"width": 1440, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
        )
        if config.USE_SAVED_SESSION and os.path.exists(config.SESSION_FILE):
            ctx_args["storage_state"] = config.SESSION_FILE
        context = browser.new_context(**ctx_args)
        page = context.new_page()
        page.set_default_timeout(15000)

        try:
            do_login(page)
            handle_2fa(page)
            select_cif(page)
            select_account_and_search(page)
            filas, total, p_ini, p_fin = expand_and_extract(page)

            try:
                context.storage_state(path=config.SESSION_FILE)
            except Exception:  # noqa: BLE001
                pass

            registros = []
            for f in filas:
                mb, tipo = parse_consumo(f.get("consumo", ""))
                registros.append({
                    "numero_linea": f["numero"],
                    "consumo_mb": mb,
                    "consumo_texto": f.get("consumo", ""),
                    "tipo_plan": tipo,
                })

            guardados = db.save_snapshot(
                registros, config.TARGET_CIF, config.TARGET_ACCOUNT, p_ini, p_fin)
            print(f"[7] Guardados {guardados} consumos en Supabase.")

            if total is not None and guardados < total * 0.9:
                estado = "parcial"
            else:
                estado = "ok"

        except Exception as e:  # noqa: BLE001
            error_msg = f"{type(e).__name__}: {e}"
            print("[ERROR]", error_msg)
            traceback.print_exc()
            dump_debug(page, "error")
        finally:
            context.close()
            browser.close()

    db.finish_run(run_id, estado, lineas_detectadas=total,
                  lineas_guardadas=guardados, mensaje_error=error_msg)
    print(f"[FIN] Estado: {estado}")
    return 0 if estado in ("ok", "parcial") else 1


class _Tee:
    """Escribe en varios streams a la vez (consola + archivo de log)."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for st in self.streams:
            try:
                st.write(data)
                st.flush()
            except Exception:  # noqa: BLE001
                pass

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:  # noqa: BLE001
                pass


def main():
    ap = argparse.ArgumentParser(description="Scraper Mi Vodafone Business -> Supabase")
    ap.add_argument("--headful", action="store_true",
                    help="Abrir el navegador visible (para depurar)")
    args = ap.parse_args()

    log_path = os.path.join(config.BASE_DIR, "last_run.log")
    logf = None
    try:
        logf = open(log_path, "w", encoding="utf-8")
        sys.stdout = _Tee(sys.__stdout__, logf)
        sys.stderr = _Tee(sys.__stderr__, logf)
    except Exception:  # noqa: BLE001
        logf = None

    print(f"=== Inicio scraper {datetime.now().isoformat()} (headful={args.headful}) ===")
    rc = 1
    try:
        rc = run(headful=args.headful)
    except Exception:  # noqa: BLE001
        print("[FATAL] Excepcion no controlada:")
        traceback.print_exc()
        rc = 1
    finally:
        print(f"=== Fin scraper (codigo {rc}) ===")
        if logf:
            try:
                logf.flush()
                logf.close()
            except Exception:  # noqa: BLE001
                pass
    sys.exit(rc)


if __name__ == "__main__":
    main()
