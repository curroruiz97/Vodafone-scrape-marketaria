"""
Capa de acceso a Supabase.

Guarda los consumos en UNA sola tabla:
  consumo_diario  -> una fila por linea y dia (numero + consumo + fecha).
Ademas registra cada ejecucion en scrape_runs (monitorizacion).

Usa la service_role key (solo en servidor) para saltarse RLS.
"""
from datetime import datetime, timezone

from supabase import create_client

import config

TABLA = "consumo_diario"


def _client():
    if not config.SUPABASE_URL or not config.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el .env")
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)


def _now():
    return datetime.now(timezone.utc).isoformat()


def start_run():
    """Crea un registro de ejecucion y devuelve su id."""
    sb = _client()
    res = sb.table("scrape_runs").insert({"estado": "en_curso"}).execute()
    return res.data[0]["id"]


def finish_run(run_id, estado, lineas_detectadas=None, lineas_guardadas=None, mensaje_error=None):
    sb = _client()
    sb.table("scrape_runs").update({
        "finalizado_en": _now(),
        "estado": estado,
        "lineas_detectadas": lineas_detectadas,
        "lineas_guardadas": lineas_guardadas,
        "mensaje_error": (mensaje_error or "")[:2000] if mensaje_error else None,
    }).eq("id", run_id).execute()


def save_snapshot(registros, cif, cuenta, periodo_inicio=None, periodo_fin=None):
    """
    registros: lista de dicts con numero_linea, consumo_mb, consumo_texto, tipo_plan.
    Hace upsert en consumo_diario (idempotente por numero_linea + fecha_captura).
    Devuelve el numero de filas guardadas.
    """
    if not registros:
        return 0

    sb = _client()
    ahora = _now()
    hoy = datetime.now(timezone.utc).date().isoformat()

    rows = [{
        "numero_linea": r["numero_linea"],
        "consumo_mb": r.get("consumo_mb"),
        "consumo_texto": r.get("consumo_texto"),
        "tipo_plan": r.get("tipo_plan"),
        "fecha_captura": hoy,
        "periodo_inicio": periodo_inicio,
        "periodo_fin": periodo_fin,
        "cif": cif,
        "cuenta": cuenta,
        "capturado_en": ahora,
    } for r in registros]

    guardados = 0
    for i in range(0, len(rows), 200):
        lote = rows[i:i + 200]
        sb.table(TABLA).upsert(lote, on_conflict="numero_linea,fecha_captura").execute()
        guardados += len(lote)

    return guardados
