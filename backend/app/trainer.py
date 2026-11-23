"""Reentrenamiento: entrena un candidato con todos los datos de la BD, lo compara con el modelo activo
sobre los años más recientes (holdout) y lo promueve solo si mejora."""
import json
from datetime import datetime, timezone

import joblib
import numpy as np

import ml_core
from . import config, db, predictor

ACCEPT_MAE, ACCEPT_MIN_IMPROVEMENT, ACCEPT_MIN_R2 = 0.65, 0.10, 0.30   # criterios definidos en la fase 1


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def acceptance(metrics, baseline):
    improvement = (baseline["mae"] - metrics["mae"]) / baseline["mae"] if baseline["mae"] else 0.0
    ok = metrics["mae"] <= ACCEPT_MAE and improvement >= ACCEPT_MIN_IMPROVEMENT and metrics["r2"] >= ACCEPT_MIN_R2
    return ok, improvement


def choose_holdout(years):
    """Primer año del holdout: los años más recientes hasta reunir MIN_HOLDOUT_ROWS películas."""
    counts = years.value_counts().sort_index(ascending=False)
    total = 0
    for yr, n in counts.items():
        total += int(n)
        if total >= config.MIN_HOLDOUT_ROWS:
            return int(yr)
    raise ValueError(f"No hay suficientes películas recientes para validar el reentrenamiento "
                     f"(se necesitan al menos {config.MIN_HOLDOUT_ROWS}).")


def retrain_once() -> dict:
    df = db.load_movies_df()
    df = df[df["score"].notna()].reset_index(drop=True)
    if len(df) < 1000:
        raise ValueError(f"Datos insuficientes para entrenar ({len(df)} filas).")
    X, y = ml_core.prepare_features(df), df["score"].astype(float)

    first_hold = choose_holdout(X["year"])
    is_tr = (X["year"] < first_hold).to_numpy()
    Xtr, ytr, Xho, yho = X[is_tr].reset_index(drop=True), y[is_tr].reset_index(drop=True), X[~is_tr], y[~is_tr]

    row, active_pipe = predictor.get_active()
    hyper = json.loads(row["hyperparameters"])
    candidate = ml_core.build_final_pipeline(row["algorithm"], hyper, row["imputation"]).fit(Xtr, ytr)
    baseline = ml_core.build_pipeline("media (baseline)").fit(Xtr, ytr)

    m_c = ml_core.regression_metrics(yho, candidate.predict(Xho))
    m_a = ml_core.regression_metrics(yho, active_pipe.predict(Xho))
    m_b = ml_core.regression_metrics(yho, baseline.predict(Xho))
    promote = m_c["mae"] < m_a["mae"]
    accepted, improvement = acceptance(m_c, m_b)

    version = db.next_version_name()
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    artifact = config.MODELS_DIR / f"model_{version}.joblib"
    joblib.dump(candidate, artifact, compress=3)
    meta = {"version": version, "algorithm": row["algorithm"], "hyperparameters": hyper,
            "imputation": row["imputation"],
            "train_years": [int(Xtr["year"].min()), first_hold - 1],
            "eval_years": [int(Xho["year"].min()), int(Xho["year"].max())],
            "n_train": int(len(Xtr)), "n_eval": int(len(Xho)),
            "eval_metrics": m_c, "baseline_metrics": m_b, "improvement": improvement,
            "accepted": accepted, "parent_eval_mae": m_a["mae"], "trained_at": _now()}
    model_id = db.register_model_version(meta, predictor.store_path(artifact), activate=promote,
                                         parent_version=row["version"])

    unfair = row["train_year_max"] is not None and row["train_year_max"] >= first_hold
    msg = (f"Holdout {meta['eval_years'][0]}–{meta['eval_years'][1]} (n={len(Xho)}), entrenado con {len(Xtr)} películas. "
           f"Candidato {version}: MAE {m_c['mae']:.3f} · activo {row['version']}: MAE {m_a['mae']:.3f} · "
           f"baseline: MAE {m_b['mae']:.3f}. ")
    msg += (f"Se PROMUEVE {version} (mejora al activo)." if promote
            else f"NO se promueve: se conserva {row['version']} (el candidato no lo mejora).")
    if unfair:
        msg += f" Aviso: el modelo activo ya había visto años del holdout; la comparación favorece al activo."
    return {"total_rows": int(len(df)), "resulting_model_version_id": model_id, "promoted": int(promote), "message": msg}


def run_retrain(run_id: int):
    """Se ejecuta en segundo plano; el estado queda en la tabla training_runs."""
    try:
        db.update_training_run(run_id, status="running")
        result = retrain_once()
        db.update_training_run(run_id, status="succeeded", finished_at=_now(), **result)
    except Exception as e:  # noqa: BLE001 - se informa al usuario vía la API
        db.update_training_run(run_id, status="failed", finished_at=_now(), message=f"{type(e).__name__}: {e}")
