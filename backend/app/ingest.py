"""Validación y lectura del archivo CSV de entrenamiento."""
import io
from collections import Counter

import numpy as np
import pandas as pd

import ml_core

REQUIRED = ["year", "score", "genre"]
KNOWN = ["name", "director", "writer", "star", "company", "rating", "country", "budget", "runtime",
         "released", "release_month"]
IGNORED_BY_DESIGN = ["votes", "gross"]          # se conocen tras el estreno: no se usan (fuga de datos)


class CsvError(ValueError):
    """El archivo no se puede aceptar (formato o columnas)."""


def parse_training_csv(content: bytes):
    """Devuelve (filas_válidas, informe). Lanza CsvError si el archivo no sirve."""
    if not content.strip():
        raise CsvError("El archivo está vacío")
    for enc in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=enc)
            break
        except UnicodeDecodeError:
            continue
        except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
            raise CsvError(f"No se pudo leer el CSV: {e}")
    else:
        raise CsvError("No se pudo decodificar el archivo (use UTF-8)")

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise CsvError(f"Faltan columnas obligatorias: {', '.join(missing)}. "
                       f"Obligatorias: {', '.join(REQUIRED)}; opcionales: {', '.join(KNOWN)}")
    received = len(df)
    ignored = [c for c in df.columns if c not in REQUIRED + KNOWN]

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    for c in ("budget", "runtime"):
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
    for c in ("name", "director", "writer", "star", "company", "rating", "country", "genre", "released", "release_month"):
        if c not in df:
            df[c] = None
    if df["release_month"].isna().all():
        df["release_month"] = df["released"].map(ml_core._month_from_released)

    reasons = Counter()
    ok = pd.Series(True, index=df.index)
    for mask, why in [(df["year"].isna() | ~df["year"].between(1888, 2100), "año inválido o ausente"),
                      (df["score"].isna() | ~df["score"].between(0, 10), "score inválido (debe estar entre 0 y 10)"),
                      (df["genre"].isna() | (df["genre"].astype(str).str.strip() == ""), "género ausente")]:
        bad = ok & mask
        reasons[why] += int(bad.sum())
        ok &= ~mask
    df = df[ok].copy()
    df["year"] = df["year"].astype(int)
    df["budget"] = df["budget"].where(df["budget"] > 0)
    df["runtime"] = df["runtime"].where(df["runtime"] > 0)
    df = df.replace({np.nan: None})
    rows = df[["name", "year", "release_month", "director", "writer", "star", "company", "genre",
               "rating", "country", "budget", "runtime", "score"]].to_dict("records")
    report = {"rows_received": received, "rows_valid": len(rows), "rows_rejected": received - len(rows),
              "rejection_reasons": {k: v for k, v in reasons.items() if v},
              "ignored_columns": ignored + [c for c in IGNORED_BY_DESIGN if c in df.columns and c not in ignored]}
    return rows, report
