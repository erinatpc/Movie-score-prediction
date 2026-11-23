"""Configuración del servicio (se puede sobrescribir con variables de entorno)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]                      # backend/
REPO_DIR = BASE_DIR.parent

DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "app.db"))
MODELS_DIR = Path(os.getenv("MODELS_DIR", BASE_DIR / "models"))
SEED_CSV = Path(os.getenv("SEED_CSV", REPO_DIR / "data" / "movies.csv"))
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"

# Orígenes del frontend autorizados por CORS (el navegador solo llama al backend; entre servicios no hace falta).
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000",
).split(",") if o.strip()]

MAX_UPLOAD_MB = 20
MIN_HOLDOUT_ROWS = 100          # mínimo de películas recientes para validar un reentrenamiento
