"""Llama a los manejadores de main.py directamente. Con FastAPI real, además se prueba por HTTP (test_api.py)."""
import asyncio

import pytest

from conftest import STUBBED


@pytest.fixture()
def main(env):
    from app import main
    return main


def test_manejadores_responden_con_el_contrato(main, env):
    from app import schemas, service
    schemas.Health.model_validate(main.health())
    schemas.Options.model_validate(main.options())
    schemas.DatasetSummary.model_validate(main.dataset())
    req = schemas.PredictRequest(genre="Drama", year=2024, director="Woody Allen")
    schemas.PredictResponse.model_validate(main.predict(req))
    schemas.PredictionsPage.model_validate(main.predictions(limit=5, offset=0))
    assert isinstance(main.models(), list)
    schemas.MetricsResponse.model_validate(main.metrics(version=None))
    with pytest.raises(service.NotFound):
        main.metrics(version="v404")
    with pytest.raises(service.NotFound):
        main.retrain_status(run_id=999)


@pytest.mark.skipif(not STUBBED, reason="con FastAPI real se usa test_api.py")
def test_subida_y_reentrenamiento_via_manejadores(main, env):
    from fastapi import BackgroundTasks, UploadFile
    csv = b"name,year,genre,score\nPelicula Uno,2021,Drama,7.1\n"
    up = asyncio.run(main.training_file(UploadFile("n.csv", csv)))
    assert up["rows_inserted"] == 1
    bt = BackgroundTasks()
    run = main.retrain(bt)
    assert run["status"] == "pending" and bt.tasks and bt.tasks[0][0].__name__ == "run_retrain"
