"""Lógica de cada endpoint (sin depender del framework web: se puede probar directamente)."""
import json

from . import config, db, ingest, predictor, schemas


class ServiceError(Exception):
    status = 400

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class NotFound(ServiceError):
    status = 404


class Conflict(ServiceError):
    status = 409


class Invalid(ServiceError):
    status = 422


class TooLarge(ServiceError):
    status = 413


class Unavailable(ServiceError):
    status = 503


def _metrics(prefix, row):
    if row.get(f"{prefix}_mae") is None:
        return None
    return {"mae": row[f"{prefix}_mae"], "rmse": row[f"{prefix}_rmse"], "r2": row[f"{prefix}_r2"]}


def model_out(row: dict) -> dict:
    return {"version": row["version"], "algorithm": row["algorithm"], "is_active": bool(row["is_active"]),
            "accepted": bool(row["accepted"]), "trained_at": row["trained_at"],
            "train_years": [row["train_year_min"], row["train_year_max"]],
            "eval_years": [row["eval_year_min"], row["eval_year_max"]],
            "n_train": row["n_train"], "n_eval": row["n_eval"],
            "cv": _metrics("cv", row), "evaluation": _metrics("eval", row), "baseline": _metrics("baseline", row),
            "improvement_vs_baseline": row["improvement"], "parent_version": row["parent_version"],
            "parent_evaluation_mae": row["parent_eval_mae"]}


def _run_out(r: dict) -> dict:
    return {"id": r["id"], "status": r["status"], "total_rows": r["total_rows"],
            "promoted": None if r["promoted"] is None else bool(r["promoted"]),
            "resulting_version": r.get("resulting_version"), "message": r["message"],
            "started_at": r["started_at"], "finished_at": r["finished_at"]}


# ---------------------------------------------------------------- endpoints
def health():
    active = db.get_active_model()
    return {"status": "ok" if active else "sin_modelo", "active_model": active["version"] if active else None,
            "movies_in_database": db.count_movies()}


def options():
    s = db.dataset_summary()
    return {"genres": db.distinct_values("genre"), "ratings": db.distinct_values("rating"),
            "countries": db.distinct_values("country"), "months": schemas.MONTHS_EN,
            "year_min": s["year_min"], "year_max": s["year_max"]}


def dataset():
    return db.dataset_summary()


def predict(request: schemas.PredictRequest):
    try:
        return predictor.predict(request.model_dump())
    except predictor.NoActiveModel as e:
        raise Unavailable(str(e))


def predictions(limit=50, offset=0):
    total, items = db.list_predictions(limit, offset)
    for it in items:
        it["known_director"] = None if it["known_director"] is None else bool(it["known_director"])
        it["budget_imputed"] = None if it["budget_imputed"] is None else bool(it["budget_imputed"])
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def models_list():
    return [model_out(r) for r in db.list_model_versions()]


def metrics(version=None):
    row = db.get_model_version(version) if version else db.get_active_model()
    if row is None:
        raise NotFound(f"La versión '{version}' no existe" if version else "No hay un modelo activo")
    return {"active": model_out(row), "history": models_list()}


def upload_training_file(filename: str, content: bytes):
    if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise TooLarge(f"El archivo supera el máximo de {config.MAX_UPLOAD_MB} MB")
    try:
        rows, report = ingest.parse_training_csv(content)
    except ingest.CsvError as e:
        raise Invalid(str(e))
    if not rows:
        raise Invalid("Ninguna fila válida en el archivo. Motivos: " + json.dumps(report["rejection_reasons"], ensure_ascii=False))
    inserted, duplicated = db.insert_movies(rows, source="upload", source_file=filename)
    return {"filename": filename, "rows_received": report["rows_received"], "rows_inserted": inserted,
            "rows_duplicated": duplicated, "rows_rejected": report["rows_rejected"],
            "rejection_reasons": report["rejection_reasons"], "ignored_columns": report["ignored_columns"],
            "total_rows_in_dataset": db.count_movies()}


def start_retrain():
    """Crea la ejecución en estado 'pending'; el trabajo pesado lo lanza el endpoint en segundo plano."""
    if db.get_running_run():
        raise Conflict("Ya hay un reentrenamiento en curso")
    if db.get_active_model() is None:
        raise Unavailable("No hay un modelo activo del que partir")
    run_id = db.create_training_run()
    return _run_out(db.get_training_run(run_id))


def retrain_status(run_id: int):
    r = db.get_training_run(run_id)
    if r is None:
        raise NotFound(f"No existe el reentrenamiento {run_id}")
    return _run_out(r)


def retrain_list(limit=20):
    return [_run_out(r) for r in db.list_training_runs(limit)]
