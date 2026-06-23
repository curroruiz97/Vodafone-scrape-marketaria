"""
Lectura del codigo de verificacion (2FA) desde el buzon IONOS por IMAP.

Estrategia robusta:
- ANTES de pedir el codigo en la web, anotamos el UID mas alto del buzon
  (get_baseline_uid): la "marca" de lo que ya existia.
- Tras pedir el codigo, consultamos repetidamente y SOLO aceptamos un correo
  con UID mayor que esa marca, del remitente de Vodafone.
- Extraccion del codigo: el codigo real es de 6 digitos. Damos prioridad al
  numero que va justo detras de "es:" y al cuerpo en TEXTO PLANO (el HTML
  contiene otros numeros, como anios de copyright, que no son el codigo).
- Lectura no destructiva (mark_seen=False).
"""
import re
import time
from datetime import datetime, timedelta, timezone

from imap_tools import MailBox


_KEYWORDS = ("vodafone", "codigo", "código", "seguridad", "logado",
             "verifica", "verificacion", "verificación", "mves", "identidad")


def get_baseline_uid(host, port, user, password):
    """Devuelve el UID mas alto del buzon en este momento (0 si falla)."""
    try:
        with MailBox(host, port).login(user, password) as mb:
            uids = []
            for m in mb.fetch(mark_seen=False, headers_only=True,
                              bulk=True, limit=80, reverse=True):
                try:
                    uids.append(int(m.uid))
                except (TypeError, ValueError):
                    pass
            base = max(uids) if uids else 0
            print(f"[3] UID base del buzon: {base}")
            return base
    except Exception as e:  # noqa: BLE001
        print(f"[3] Aviso: no se pudo leer el UID base ({e}); sigo sin marca.")
        return 0


def _extract_code(text, code_re):
    """Extrae el codigo de 6 digitos de un cuerpo de correo."""
    if not text:
        return None
    # 1) Preferencia: 6 digitos justo detras de "es" (".. Business es: 089987").
    m = re.search(r"\bes:?\s*(\d{6})\b", text, re.I)
    if m:
        return m.group(1)
    # 2) Cualquier numero de exactamente 6 digitos.
    m = code_re.search(text)
    if m:
        return m.group(1)
    return None


def _find_code(msgs, cutoff, sender, code_re, min_uid=0):
    """Devuelve el codigo del correo NUEVO mas reciente que cumpla los filtros."""
    best = None  # (uid, code)
    for msg in msgs:
        try:
            uid = int(msg.uid) if msg.uid else 0
        except (TypeError, ValueError):
            uid = 0
        if min_uid and uid <= min_uid:
            continue

        msg_dt = msg.date
        if msg_dt is not None:
            if msg_dt.tzinfo is None:
                msg_dt = msg_dt.replace(tzinfo=timezone.utc)
            if cutoff and msg_dt < cutoff:
                continue

        frm = (msg.from_ or "").lower()
        if sender and sender.lower() not in frm:
            continue

        blob = " ".join(filter(None, [msg.subject, msg.text, msg.html])).lower()
        parece_vodafone = (
            (sender and sender.lower() in frm)
            or any(k in frm for k in ("vodafone", "mves"))
            or any(k in blob for k in _KEYWORDS)
        )
        if not parece_vodafone:
            continue

        # Preferir el cuerpo en TEXTO PLANO; si no, el HTML.
        code = _extract_code(msg.text or "", code_re) or _extract_code(msg.html or "", code_re)
        if code and (best is None or uid > best[0]):
            best = (uid, code)
    return best[1] if best else None


def fetch_otp_code(host, port, user, password, since_dt,
                   sender="", regex=r"\b(\d{6})\b",
                   timeout=120, poll_interval=5, initial_wait=5,
                   min_attempts=3, min_uid=0):
    """Devuelve el codigo OTP como string, o lanza TimeoutError si no llega."""
    code_re = re.compile(regex)
    cutoff = since_dt - timedelta(seconds=180)

    if initial_wait > 0:
        print(f"[3] Esperando {initial_wait}s a que llegue el correo con el codigo...")
        time.sleep(initial_wait)

    deadline = time.time() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            with MailBox(host, port).login(user, password) as mb:
                msgs = mb.fetch(mark_seen=False, reverse=True, bulk=True, limit=30)
                code = _find_code(msgs, cutoff, sender, code_re, min_uid=min_uid)
            if code:
                print(f"[3] Codigo NUEVO encontrado en el intento {attempt}: {code}")
                return code
            print(f"[3] Intento {attempt}: aun no ha llegado el correo nuevo. "
                  f"Reintento en {poll_interval}s...")
        except Exception as e:  # noqa: BLE001
            print(f"[3] Intento {attempt}: aviso al leer el buzon ({e}). "
                  f"Reintento en {poll_interval}s...")

        if time.time() >= deadline and attempt >= min_attempts:
            break
        time.sleep(poll_interval)

    raise TimeoutError(
        "No llego el correo NUEVO con el codigo dentro del tiempo limite. "
        "Revisa IMAP_USER/IMAP_PASS, que IMAP este activado en IONOS, "
        "o sube OTP_TIMEOUT en el .env."
    )


def now_utc():
    return datetime.now(timezone.utc)
