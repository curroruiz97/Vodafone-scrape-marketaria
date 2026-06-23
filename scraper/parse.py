"""
Funciones de normalización de los textos de consumo y periodo.
Sin dependencias externas (solo stdlib) para poder testearlas aisladamente:
    python parse.py    # ejecuta unos casos de prueba
"""
import re
import unicodedata
from datetime import datetime

_UNIDADES_A_MB = {"B": 1 / (1024 * 1024), "KB": 1 / 1024, "MB": 1.0,
                  "GB": 1024.0, "TB": 1024.0 * 1024.0}

_MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
          "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}


def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _to_float(num_str):
    s = num_str.strip()
    if "," in s:           # formato español: "1.234,5" -> miles '.', decimal ','
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def parse_consumo(texto):
    """'Consumido 0 MB de tus datos ilimitados' -> (consumo_mb, tipo_plan)."""
    if not texto:
        return None, None
    tipo = "ilimitado" if re.search("ilimitad", texto, re.I) else None
    m = re.search(r"([\d.,]+)\s*(TB|GB|MB|KB|B)\b", texto, re.I)
    if not m:
        return None, tipo
    try:
        valor = _to_float(m.group(1))
    except ValueError:
        return None, tipo
    mb = valor * _UNIDADES_A_MB[m.group(2).upper()]
    return round(mb, 3), tipo


def parse_periodo(texto):
    """'Periodo de consumo 1 Jun - 18 Jun' -> (inicio_iso, fin_iso) o (None, None)."""
    if not texto:
        return None, None
    pares = re.findall(r"(\d{1,2})\s*([A-Za-zÁÉÍÓÚáéíóúÑñ]{3,})", texto)
    if len(pares) < 2:
        return None, None
    year = datetime.now().year

    def to_date(dia, mes_txt):
        mes = _MESES.get(_strip_accents(mes_txt).lower()[:3])
        if not mes:
            return None
        return datetime(year, mes, int(dia)).date()

    ini = to_date(*pares[0])
    fin = to_date(*pares[1])
    if ini and fin and fin < ini:        # cruce de año
        fin = fin.replace(year=year + 1)
    return (ini.isoformat() if ini else None, fin.isoformat() if fin else None)


if __name__ == "__main__":
    casos = [
        ("Consumido 0 MB de tus datos ilimitados", (0.0, "ilimitado")),
        ("Consumido 1,2 GB de tus datos ilimitados", (1228.8, "ilimitado")),
        ("Consumido 1.234,5 MB", (1234.5, None)),
        ("Consumido 512 KB de datos", (0.5, None)),
        ("Consumido 2 GB", (2048.0, None)),
        ("texto sin consumo", (None, None)),
    ]
    ok = True
    for texto, esperado in casos:
        got = parse_consumo(texto)
        estado = "OK " if got == esperado else "FALLO"
        if got != esperado:
            ok = False
        print(f"[{estado}] parse_consumo({texto!r}) -> {got}  (esperado {esperado})")

    año = datetime.now().year
    pcasos = [
        ("Periodo de consumo 1 Jun - 18 Jun", (f"{año}-06-01", f"{año}-06-18")),
        ("Periodo de consumo 28 Dic - 5 Ene", (f"{año}-12-28", f"{año + 1}-01-05")),
    ]
    for texto, esperado in pcasos:
        got = parse_periodo(texto)
        estado = "OK " if got == esperado else "FALLO"
        if got != esperado:
            ok = False
        print(f"[{estado}] parse_periodo({texto!r}) -> {got}  (esperado {esperado})")

    print("\nTODO OK" if ok else "\nHAY FALLOS")
