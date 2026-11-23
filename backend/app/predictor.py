"""Carga del modelo activo y predicción."""
import threading
from pathlib import Path

import joblib
import pandas as pd

import ml_core
from . import config, db

_lock = threading.Lock()
_cache = {"version": None, "pipeline": None}


class NoActiveModel(RuntimeError):
    pass


def resolve_artifact(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else config.BASE_DIR / p


def store_path(path: Path) -> str:
    """Ruta relativa a backend/ cuando es posible (portable entre equipos)."""
    try:
        return str(Path(path).resolve().relative_to(config.BASE_DIR)).replace("\\", "/")
    except ValueError:
        return str(path)


def get_active():
    """(fila de BD, pipeline) del modelo activo. Recarga solo si cambió la versión activa."""
    row = db.get_active_model()
    if row is None:
        raise NoActiveModel("No hay ningún modelo activo")
    with _lock:
        if _cache["version"] != row["version"]:
            _cache["pipeline"] = joblib.load(resolve_artifact(row["artifact_path"]))
            _cache["version"] = row["version"]
        return row, _cache["pipeline"]


def predict(data: dict) -> dict:
    """Predice el score de una película y guarda el resultado en el historial."""
    row, pipe = get_active()
    record = {k: v for k, v in data.items() if v is not None}
    X = ml_core.prepare_features(pd.DataFrame([record]))
    score = round(min(10.0, max(0.0, float(pipe.predict(X)[0]))), 2)

    n_prev = ml_core.entity_history(pipe, "director", data.get("director"), data["year"])
    known = None if n_prev is None else n_prev > 0
    budget_imputed = bool(X["budget_missing"].iloc[0])

    warnings = []
    if not data.get("director"):
        warnings.append("No se indicó director: la estimación es menos fiable.")
    elif known is False:
        warnings.append("El director no tiene películas previas en los datos de entrenamiento: "
                        "la estimación es menos fiable (el error medio es mayor en estos casos).")
    if budget_imputed:
        warnings.append("Presupuesto no informado: se estimó con la mediana de su género y época.")
    if data["year"] > row["eval_year_max"] + 2:
        warnings.append(f"El año {data['year']} está fuera del rango de datos ({row['train_year_min']}–{row['eval_year_max']}): "
                        "la estimación es una extrapolación.")

    pid = db.add_prediction(row["id"], record, score, known, budget_imputed)
    return {"prediction_id": pid, "predicted_score": score, "model_version": row["version"],
            "known_director": known, "director_previous_films": n_prev,
            "budget_imputed": budget_imputed, "warnings": warnings}
