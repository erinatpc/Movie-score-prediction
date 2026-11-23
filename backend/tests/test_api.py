"""Pruebas HTTP de la API real con FastAPI + TestClient (requieren `pip install fastapi httpx`)."""
import pytest

from conftest import STUBBED

pytestmark = pytest.mark.skipif(STUBBED, reason="FastAPI no está instalado")

BODY = {"name": "Prueba", "director": "Woody Allen", "genre": "Comedy", "year": 2022, "budget": 20_000_000, "runtime": 100}


@pytest.fixture()
def client(env):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_health_y_documentacion(client):
    assert client.get("/health").json()["active_model"] == "v1"
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert {"/predict", "/predictions", "/metrics", "/retrain", "/training-file"} <= set(spec["paths"])


def test_predict_y_validacion(client):
    r = client.post("/predict", json=BODY)
    assert r.status_code == 200 and 0 <= r.json()["predicted_score"] <= 10
    assert client.post("/predict", json={**BODY, "year": 1800}).status_code == 422
    assert client.post("/predict", json={"year": 2022}).status_code == 422          # falta género


def test_historial_y_metricas(client):
    client.post("/predict", json=BODY)
    page = client.get("/predictions?limit=5").json()
    assert page["total"] == 1 and page["items"][0]["input"]["director"] == "Woody Allen"
    assert client.get("/predictions?limit=0").status_code == 422
    m = client.get("/metrics").json()
    assert m["active"]["version"] == "v1" and client.get("/metrics?version=v99").status_code == 404


def test_cors_permite_el_frontend(client):
    r = client.options("/predict", headers={"Origin": "http://localhost:5500", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5500"
    r = client.get("/health", headers={"Origin": "http://sitio-no-autorizado.example"})
    assert "access-control-allow-origin" not in r.headers


def test_subida_y_reentrenamiento(client):
    from app import config
    demo = config.REPO_DIR / "data" / "demo_nuevas_peliculas_2017_2020.csv"
    r = client.post("/training-file", files={"file": (demo.name, demo.read_bytes(), "text/csv")})
    assert r.status_code == 200 and r.json()["rows_inserted"] > 500
    bad = client.post("/training-file", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert bad.status_code == 422
    run = client.post("/retrain")
    assert run.status_code == 202
    # TestClient ejecuta las tareas en segundo plano antes de devolver la respuesta
    st = client.get(f"/retrain/{run.json()['id']}").json()
    assert st["status"] == "succeeded", st["message"]
    assert len(client.get("/models").json()) == 2
