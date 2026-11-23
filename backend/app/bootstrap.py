"""Inicialización: crea la BD, registra el modelo inicial y carga los datos de entrenamiento."""
import json

from . import config, db, ingest, predictor


def register_initial_model():
    meta_path = config.MODELS_DIR / "model_v1_metadata.json"
    artifact = config.MODELS_DIR / "model_v1.joblib"
    if not meta_path.exists() or not artifact.exists():
        raise FileNotFoundError(
            f"No se encontró el modelo inicial ({artifact.name}). Ejecute notebooks/modelo_peliculas.ipynb "
            f"para generarlo en {config.MODELS_DIR}.")
    m = json.loads(meta_path.read_text(encoding="utf-8"))
    meta = {"version": m["model_version"], "algorithm": m["algorithm"], "hyperparameters": m["hyperparameters"],
            "imputation": m["imputation"], "train_years": m["train_years"], "eval_years": m["test_years"],
            "n_train": m["n_train"], "n_eval": m["n_test"], "cv_metrics": m.get("cv_metrics"),
            "eval_metrics": m["test_metrics"], "baseline_metrics": m["baseline_test_metrics"],
            "improvement": m["improvement_vs_baseline"], "accepted": m["accepted"], "trained_at": m["trained_at"]}
    db.register_model_version(meta, predictor.store_path(artifact), activate=True)


def seed_movies():
    """Carga inicial: las películas con las que se entrenó el modelo inicial (hasta su último año de train)."""
    active = db.get_active_model()
    rows, _ = ingest.parse_training_csv(config.SEED_CSV.read_bytes())
    rows = [r for r in rows if r["year"] <= active["train_year_max"]]
    inserted, _ = db.insert_movies(rows, source="seed", source_file=config.SEED_CSV.name)
    return inserted


def bootstrap():
    db.init_db()
    db.fail_stale_runs()
    if not db.list_model_versions():
        register_initial_model()
    if db.count_movies() == 0:
        seed_movies()
