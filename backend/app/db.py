"""Acceso a la base de datos SQLite (librería estándar, sin ORM)."""
import json
import sqlite3
from contextlib import contextmanager

import pandas as pd

from . import config

MOVIE_COLS = ["name", "year", "release_month", "director", "writer", "star", "company", "genre",
              "rating", "country", "budget", "runtime", "score"]


@contextmanager
def connect():
    """Una conexión por operación (seguro entre hilos); confirma al salir o revierte si hay error."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with connect() as con:
        con.executescript(config.SCHEMA_PATH.read_text(encoding="utf-8"))


def _row(r):
    return dict(r) if r is not None else None


# ------------------------------------------------------------------ películas (datos de entrenamiento)
def count_movies():
    with connect() as con:
        return con.execute("SELECT COUNT(*) FROM movies").fetchone()[0]


def insert_movies(rows, source, source_file=None):
    """Inserta ignorando duplicados (name, year). Devuelve (insertadas, duplicadas)."""
    sql = f"""INSERT OR IGNORE INTO movies ({', '.join(MOVIE_COLS)}, source, source_file)
              VALUES ({', '.join('?' * len(MOVIE_COLS))}, ?, ?)"""
    with connect() as con:
        before = con.total_changes
        con.executemany(sql, [[r.get(c) for c in MOVIE_COLS] + [source, source_file] for r in rows])
        inserted = con.total_changes - before
    return inserted, len(rows) - inserted


def load_movies_df():
    """Todos los datos de entrenamiento como DataFrame crudo (columnas de MOVIE_COLS)."""
    with connect() as con:
        return pd.read_sql_query(f"SELECT {', '.join(MOVIE_COLS)} FROM movies", con)


def dataset_summary():
    with connect() as con:
        tot = con.execute("SELECT COUNT(*) n, MIN(year) y0, MAX(year) y1 FROM movies").fetchone()
        by = con.execute("SELECT source, COUNT(*) n FROM movies GROUP BY source").fetchall()
    return {"total_rows": tot["n"], "year_min": tot["y0"], "year_max": tot["y1"],
            "by_source": {r["source"]: r["n"] for r in by}}


def distinct_values(column, limit=60):
    assert column in {"genre", "rating", "country"}
    with connect() as con:
        rows = con.execute(
            f"SELECT {column} v, COUNT(*) n FROM movies WHERE {column} IS NOT NULL "
            f"GROUP BY {column} ORDER BY n DESC LIMIT ?", (limit,)).fetchall()
    return [r["v"] for r in rows]


# ------------------------------------------------------------------ modelos
def register_model_version(meta: dict, artifact_path: str, activate: bool, parent_version=None):
    """Guarda una versión con sus métricas. `meta` usa las claves del JSON de metadatos."""
    cv, ev, bl = meta.get("cv_metrics") or {}, meta["eval_metrics"], meta["baseline_metrics"]
    with connect() as con:
        if activate:
            con.execute("UPDATE model_versions SET is_active = 0 WHERE is_active = 1")
        cur = con.execute(
            """INSERT INTO model_versions (version, algorithm, hyperparameters, imputation,
                 train_year_min, train_year_max, eval_year_min, eval_year_max, n_train, n_eval,
                 cv_mae, cv_rmse, cv_r2, eval_mae, eval_rmse, eval_r2,
                 baseline_mae, baseline_rmse, baseline_r2, improvement, accepted, is_active,
                 parent_version, parent_eval_mae, artifact_path, trained_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (meta["version"], meta["algorithm"], json.dumps(meta["hyperparameters"]), meta["imputation"],
             meta["train_years"][0], meta["train_years"][1], meta["eval_years"][0], meta["eval_years"][1],
             meta["n_train"], meta["n_eval"],
             cv.get("mae"), cv.get("rmse"), cv.get("r2"), ev["mae"], ev["rmse"], ev["r2"],
             bl["mae"], bl["rmse"], bl["r2"], meta["improvement"], int(meta["accepted"]), int(activate),
             parent_version, meta.get("parent_eval_mae"), str(artifact_path), meta["trained_at"]))
        return cur.lastrowid


def get_active_model():
    with connect() as con:
        return _row(con.execute("SELECT * FROM model_versions WHERE is_active = 1").fetchone())


def get_model_version(version):
    with connect() as con:
        return _row(con.execute("SELECT * FROM model_versions WHERE version = ?", (version,)).fetchone())


def list_model_versions():
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM model_versions ORDER BY id DESC").fetchall()]


def next_version_name():
    with connect() as con:
        n = con.execute("SELECT COUNT(*) FROM model_versions").fetchone()[0]
    return f"v{n + 1}"


# ------------------------------------------------------------------ predicciones
def add_prediction(model_version_id, input_data: dict, score, known_director, budget_imputed):
    with connect() as con:
        cur = con.execute(
            """INSERT INTO predictions (model_version_id, input_json, predicted_score, known_director, budget_imputed)
               VALUES (?,?,?,?,?)""",
            (model_version_id, json.dumps(input_data, ensure_ascii=False), score,
             None if known_director is None else int(known_director), int(budget_imputed)))
        return cur.lastrowid


def list_predictions(limit=50, offset=0):
    with connect() as con:
        total = con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        rows = con.execute(
            """SELECT p.id, p.input_json, p.predicted_score, p.known_director, p.budget_imputed, p.created_at,
                      m.version AS model_version
               FROM predictions p JOIN model_versions m ON m.id = p.model_version_id
               ORDER BY p.id DESC LIMIT ? OFFSET ?""", (limit, offset)).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        d["input"] = json.loads(d.pop("input_json"))
        items.append(d)
    return total, items


# ------------------------------------------------------------------ reentrenamientos
def create_training_run():
    with connect() as con:
        cur = con.execute("INSERT INTO training_runs (status) VALUES ('pending')")
        return cur.lastrowid


def get_running_run():
    with connect() as con:
        return _row(con.execute(
            "SELECT * FROM training_runs WHERE status IN ('pending','running') ORDER BY id DESC LIMIT 1").fetchone())


def update_training_run(run_id, **fields):
    allowed = {"status", "total_rows", "resulting_model_version_id", "promoted", "message", "finished_at"}
    assert set(fields) <= allowed
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    with connect() as con:
        con.execute(f"UPDATE training_runs SET {sets} WHERE id = ?", [*fields.values(), run_id])


def get_training_run(run_id):
    with connect() as con:
        return _row(con.execute(
            """SELECT r.*, m.version AS resulting_version FROM training_runs r
               LEFT JOIN model_versions m ON m.id = r.resulting_model_version_id WHERE r.id = ?""",
            (run_id,)).fetchone())


def list_training_runs(limit=20):
    with connect() as con:
        return [dict(r) for r in con.execute(
            """SELECT r.*, m.version AS resulting_version FROM training_runs r
               LEFT JOIN model_versions m ON m.id = r.resulting_model_version_id
               ORDER BY r.id DESC LIMIT ?""", (limit,)).fetchall()]


def fail_stale_runs():
    """Si el servicio se reinició durante un reentrenamiento, esa ejecución quedó interrumpida."""
    with connect() as con:
        con.execute("""UPDATE training_runs SET status='failed', message='Interrumpido por reinicio del servicio',
                       finished_at=datetime('now') WHERE status IN ('pending','running')""")
