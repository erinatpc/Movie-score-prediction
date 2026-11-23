

PRAGMA foreign_keys = ON;

-- Datos de entrenamiento: carga inicial + archivos subidos por la API.
CREATE TABLE IF NOT EXISTS movies (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT,
    year           INTEGER NOT NULL CHECK (year BETWEEN 1888 AND 2100),
    release_month  TEXT,
    director       TEXT,
    writer         TEXT,
    star           TEXT,
    company        TEXT,
    genre          TEXT NOT NULL,
    rating         TEXT,
    country        TEXT,
    budget         REAL CHECK (budget IS NULL OR budget > 0),
    runtime        REAL CHECK (runtime IS NULL OR runtime > 0),
    score          REAL NOT NULL CHECK (score BETWEEN 0 AND 10),
    source         TEXT NOT NULL DEFAULT 'seed' CHECK (source IN ('seed', 'upload')),
    source_file    TEXT,
    added_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (name, year)
);
CREATE INDEX IF NOT EXISTS idx_movies_year ON movies (year);

-- Versiones del modelo y sus métricas.
CREATE TABLE IF NOT EXISTS model_versions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    version          TEXT NOT NULL UNIQUE,                 -- v1, v2, ...
    algorithm        TEXT NOT NULL,
    hyperparameters  TEXT NOT NULL,                        -- JSON
    imputation       TEXT NOT NULL,
    train_year_min   INTEGER,
    train_year_max   INTEGER,
    eval_year_min    INTEGER,
    eval_year_max    INTEGER,
    n_train          INTEGER,
    n_eval           INTEGER,
    cv_mae           REAL, cv_rmse REAL, cv_r2 REAL,        -- validación cruzada temporal (solo v1)
    eval_mae         REAL, eval_rmse REAL, eval_r2 REAL,    -- test ciego (v1) o holdout (reentrenos)
    baseline_mae     REAL, baseline_rmse REAL, baseline_r2 REAL,
    improvement      REAL,                                  -- mejora relativa del MAE frente al baseline
    accepted         INTEGER NOT NULL DEFAULT 0 CHECK (accepted IN (0, 1)),
    is_active        INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    parent_version   TEXT,                                  -- versión que se intentó superar
    parent_eval_mae  REAL,                                  -- MAE de esa versión sobre el MISMO conjunto de evaluación
    artifact_path    TEXT NOT NULL,                         -- archivo .joblib
    trained_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Solo puede haber un modelo activo.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_model ON model_versions (is_active) WHERE is_active = 1;

-- Historial de predicciones: datos enviados y resultado.
CREATE TABLE IF NOT EXISTS predictions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version_id   INTEGER NOT NULL REFERENCES model_versions (id),
    input_json         TEXT NOT NULL,
    predicted_score    REAL NOT NULL,
    known_director     INTEGER,
    budget_imputed     INTEGER,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions (created_at);

-- Ejecuciones de reentrenamiento.
CREATE TABLE IF NOT EXISTS training_runs (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    status                    TEXT NOT NULL CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    total_rows                INTEGER,
    resulting_model_version_id INTEGER REFERENCES model_versions (id),
    promoted                  INTEGER CHECK (promoted IS NULL OR promoted IN (0, 1)),
    message                   TEXT,
    started_at                TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at               TEXT
);
