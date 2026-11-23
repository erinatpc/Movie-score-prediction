"""Pruebas de la lógica del servicio (no requieren FastAPI)."""
import io
import json

import pandas as pd
import pytest

import ml_core
from app import config, db, ingest, predictor, schemas, service, trainer

DEMO_CSV = config.REPO_DIR / "data" / "demo_nuevas_peliculas_2017_2020.csv"

BASE_REQ = {"name": "Prueba", "director": "Christopher Nolan", "genre": "Drama", "year": 2024,
            "budget": 100_000_000, "runtime": 150, "release_month": "July", "country": "United States",
            "rating": "PG-13"}


def test_bootstrap_registra_modelo_y_carga_datos(env):
    active = db.get_active_model()
    assert active["version"] == "v1" and active["is_active"] == 1
    assert db.count_movies() == active["n_train"]                # se cargó exactamente el train del modelo
    assert db.dataset_summary()["year_max"] == active["train_year_max"]
    assert service.health()["status"] == "ok"


def test_bootstrap_es_idempotente(env):
    from app import bootstrap
    n = db.count_movies()
    bootstrap.bootstrap()
    assert db.count_movies() == n and len(db.list_model_versions()) == 1


def test_variables_prohibidas_no_entran_al_modelo():
    df = pd.DataFrame([{**BASE_REQ, "votes": 1e6, "gross": 9e8, "released": "July 1, 2024 (United States)"}])
    X = ml_core.prepare_features(df)
    assert not set(ml_core.FORBIDDEN_COLS) & set(X.columns)
    assert list(X.columns) == ml_core.INPUT_COLS


def test_prediccion_valida_y_queda_en_el_historial(env):
    out = service.predict(schemas.PredictRequest(**BASE_REQ))
    assert 0 <= out["predicted_score"] <= 10 and out["model_version"] == "v1"
    assert out["known_director"] is True and out["director_previous_films"] > 0
    assert out["budget_imputed"] is False
    page = service.predictions(limit=10, offset=0)
    assert page["total"] == 1 and page["items"][0]["input"]["director"] == "Christopher Nolan"
    schemas.PredictionsPage.model_validate(page)
    schemas.PredictResponse.model_validate(out)


def test_prediccion_ignora_votes_y_gross(env):
    a = service.predict(schemas.PredictRequest(**BASE_REQ))["predicted_score"]
    b = service.predict(schemas.PredictRequest(**BASE_REQ, votes=2_000_000, gross=1e9))["predicted_score"]
    assert a == b


def test_director_nuevo_y_presupuesto_faltante(env):
    out = service.predict(schemas.PredictRequest(director="Director Inexistente XYZ", genre="Comedy", year=2023))
    assert out["known_director"] is False and out["budget_imputed"] is True
    assert any("director" in w.lower() for w in out["warnings"]) and any("presupuesto" in w.lower() for w in out["warnings"])


def test_validacion_de_entrada():
    with pytest.raises(Exception):
        schemas.PredictRequest(genre="Drama", year=1800)
    with pytest.raises(Exception):
        schemas.PredictRequest(genre="Drama", year=2024, budget=-5)
    with pytest.raises(Exception):
        schemas.PredictRequest(year=2024)                                    # falta género
    assert schemas.PredictRequest(genre="Drama", year=2024, release_month="julio").release_month == "July"
    assert schemas.PredictRequest(genre="Drama", year=2024, release_month=3).release_month == "March"


def test_metricas_y_modelos(env):
    m = service.metrics()
    schemas.MetricsResponse.model_validate(m)
    assert m["active"]["version"] == "v1" and m["active"]["evaluation"]["mae"] < m["active"]["baseline"]["mae"]
    assert m["active"]["cv"] is not None and len(service.models_list()) == 1
    with pytest.raises(service.NotFound):
        service.metrics("v99")


def test_carga_csv_validaciones():
    with pytest.raises(ingest.CsvError):
        ingest.parse_training_csv(b"")
    with pytest.raises(ingest.CsvError):
        ingest.parse_training_csv(b"a,b\n1,2\n")                              # faltan columnas
    csv = (b"name,year,genre,score,votes,director\nA,2021,Drama,7.5,100,X\nB,abc,Drama,6,1,Y\n"
           b"C,2021,Drama,15,1,Z\nD,2021,,5,1,W\nE,2022,Comedy,6.1,5,V\n")
    rows, rep = ingest.parse_training_csv(csv)
    assert rep["rows_received"] == 5 and len(rows) == 2 and rep["rows_rejected"] == 3
    assert "votes" in rep["ignored_columns"]


def test_subida_duplicados_y_limite(env):
    csv = b"name,year,genre,score\nPelicula Nueva,2021,Drama,7.1\nOtra,2021,Comedy,5.5\n"
    r1 = service.upload_training_file("nuevas.csv", csv)
    assert r1["rows_inserted"] == 2 and r1["rows_duplicated"] == 0
    r2 = service.upload_training_file("nuevas.csv", csv)
    assert r2["rows_inserted"] == 0 and r2["rows_duplicated"] == 2
    schemas.UploadResponse.model_validate(r2)
    with pytest.raises(service.Invalid):
        service.upload_training_file("malo.csv", b"x,y\n1,2\n")
    with pytest.raises(service.TooLarge):
        service.upload_training_file("grande.csv", b"x" * (config.MAX_UPLOAD_MB * 1024 * 1024 + 1))


def test_reentrenamiento_completo(env):
    assert DEMO_CSV.exists(), "falta data/demo_nuevas_peliculas_2017_2020.csv"
    up = service.upload_training_file(DEMO_CSV.name, DEMO_CSV.read_bytes())
    assert up["rows_inserted"] > 500 and "votes" in up["ignored_columns"] and "gross" in up["ignored_columns"]

    run = service.start_retrain()
    assert run["status"] == "pending"
    with pytest.raises(service.Conflict):                                    # no se permiten dos a la vez
        service.start_retrain()
    trainer.run_retrain(run["id"])                                           # el endpoint lo hace en segundo plano

    st = service.retrain_status(run["id"])
    schemas.TrainingRunOut.model_validate(st)
    assert st["status"] == "succeeded", st["message"]
    assert st["resulting_version"] == "v2" and st["total_rows"] == db.count_movies()
    versions = {m["version"]: m for m in service.models_list()}
    assert set(versions) == {"v1", "v2"} and versions["v2"]["parent_version"] == "v1"
    assert versions["v2"]["train_years"][1] < versions["v2"]["eval_years"][0]      # holdout posterior al train
    assert versions["v2"]["parent_evaluation_mae"] is not None            # comparación en el mismo holdout
    assert versions["v2"]["is_active"] == (st["promoted"] is True)
    assert st["promoted"] == (versions["v2"]["evaluation"]["mae"] < versions["v2"]["parent_evaluation_mae"])
    assert sum(m["is_active"] for m in versions.values()) == 1                    # siempre un único activo
    # tras el reentrenamiento, la API predice con el modelo activo (v1 o v2 según la promoción)
    assert service.predict(schemas.PredictRequest(**BASE_REQ))["model_version"] == ("v2" if st["promoted"] else "v1")
    assert service.retrain_list()[0]["id"] == run["id"]


def test_reentrenamiento_sin_holdout_suficiente(env, monkeypatch):
    monkeypatch.setattr(config, "MIN_HOLDOUT_ROWS", 10**9)
    run = service.start_retrain()
    trainer.run_retrain(run["id"])
    st = service.retrain_status(run["id"])
    assert st["status"] == "failed" and "suficientes" in st["message"]
    assert len(db.list_model_versions()) == 1                                 # no se guardó nada


def test_ejecuciones_interrumpidas_se_marcan_fallidas(env):
    run = service.start_retrain()
    db.fail_stale_runs()
    assert service.retrain_status(run["id"])["status"] == "failed"
