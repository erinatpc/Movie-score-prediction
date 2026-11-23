"""Exporta el contrato de la API (Swagger/OpenAPI) a docs/openapi.json.
Uso (desde backend/):  python -m app.export_openapi
"""
import json

from . import config
from .main import app

out = config.REPO_DIR / "docs" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False), encoding="utf-8")
print("Escrito:", out)
