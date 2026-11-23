import shutil
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))               # para `import ml_core` y `import app`
sys.path.insert(0, str(Path(__file__).parent))

import _fastapi_stub  # noqa: E402

STUBBED = _fastapi_stub.install()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Entorno aislado: BD temporal y copia de los modelos (el reentrenamiento escribe artefactos nuevos)."""
    from app import config, predictor
    models = tmp_path / "models"
    shutil.copytree(config.BASE_DIR / "models", models)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "app.db")
    monkeypatch.setattr(config, "MODELS_DIR", models)
    predictor._cache.update(version=None, pipeline=None)
    from app import bootstrap
    bootstrap.bootstrap()
    return tmp_path
