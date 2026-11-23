"""Contratos de la API (se reflejan automáticamente en Swagger / OpenAPI)."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def normalize_month(v):
    """Acepta 1-12, nombre en inglés o en español; devuelve el nombre en inglés (el del entrenamiento)."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()):
        n = int(v)
        if 1 <= n <= 12:
            return MONTHS_EN[n - 1]
        raise ValueError("El mes debe estar entre 1 y 12")
    t = str(v).strip().lower()
    for en, es in zip(MONTHS_EN, MONTHS_ES):
        if t in (en.lower(), es, en.lower()[:3]):
            return en
    raise ValueError("Mes no reconocido")


class PredictRequest(BaseModel):
    """Datos conocidos ANTES de producir la película. Los campos extra (votes, gross…) se ignoran."""
    model_config = ConfigDict(extra="ignore", json_schema_extra={"example": {
        "name": "Mi película", "director": "Christopher Nolan", "writer": "Christopher Nolan",
        "star": "Leonardo DiCaprio", "company": "Warner Bros.", "genre": "Drama", "rating": "PG-13",
        "country": "United States", "year": 2024, "release_month": "July", "budget": 100000000, "runtime": 150}})

    name: Optional[str] = Field(None, max_length=200, description="Título (solo se guarda en el historial; no lo usa el modelo)")
    director: Optional[str] = Field(None, max_length=120)
    writer: Optional[str] = Field(None, max_length=120)
    star: Optional[str] = Field(None, max_length=120)
    company: Optional[str] = Field(None, max_length=120)
    genre: str = Field(..., min_length=1, max_length=60, examples=["Drama"])
    rating: Optional[str] = Field(None, max_length=20, examples=["PG-13"])
    country: Optional[str] = Field(None, max_length=80, examples=["United States"])
    year: int = Field(..., ge=1900, le=2100, description="Año previsto de estreno")
    release_month: Optional[str] = Field(None, description="Mes de estreno (1-12, en inglés o español)")
    budget: Optional[float] = Field(None, gt=0, le=5e9, description="Presupuesto en USD. Si falta se imputa.")
    runtime: Optional[float] = Field(None, ge=30, le=400, description="Duración en minutos")

    @field_validator("release_month", mode="before")
    @classmethod
    def _month(cls, v):
        return normalize_month(v)

    @field_validator("name", "director", "writer", "star", "company", "rating", "country", "genre", mode="before")
    @classmethod
    def _strip(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class PredictResponse(BaseModel):
    prediction_id: int
    predicted_score: float = Field(..., description="Score estimado (escala 0-10)")
    model_version: str
    known_director: Optional[bool] = Field(None, description="¿El director tenía películas previas en el entrenamiento?")
    director_previous_films: Optional[int] = None
    budget_imputed: bool
    warnings: List[str] = []


class PredictionItem(BaseModel):
    id: int
    created_at: str
    model_version: str
    input: Dict[str, Any]
    predicted_score: float
    known_director: Optional[bool] = None
    budget_imputed: Optional[bool] = None


class PredictionsPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[PredictionItem]


class Metrics(BaseModel):
    mae: float
    rmse: float
    r2: float


class ModelVersionOut(BaseModel):
    version: str
    algorithm: str
    is_active: bool
    accepted: bool
    trained_at: str
    train_years: List[int]
    eval_years: List[int]
    n_train: Optional[int] = None
    n_eval: Optional[int] = None
    cv: Optional[Metrics] = Field(None, description="Validación cruzada temporal (solo el modelo inicial)")
    evaluation: Metrics = Field(..., description="Test ciego (v1) o holdout reciente (reentrenamientos)")
    baseline: Metrics = Field(..., description="Predecir siempre la media: referencia que hay que superar")
    improvement_vs_baseline: float = Field(..., description="Reducción relativa del MAE frente al baseline (0-1)")
    parent_version: Optional[str] = None
    parent_evaluation_mae: Optional[float] = Field(
        None, description="MAE de la versión anterior (parent_version) sobre el mismo conjunto de evaluación")


class MetricsResponse(BaseModel):
    active: ModelVersionOut
    history: List[ModelVersionOut]


class Options(BaseModel):
    genres: List[str]
    ratings: List[str]
    countries: List[str]
    months: List[str]
    year_min: Optional[int] = None
    year_max: Optional[int] = None


class DatasetSummary(BaseModel):
    total_rows: int
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    by_source: Dict[str, int]


class UploadResponse(BaseModel):
    filename: str
    rows_received: int
    rows_inserted: int
    rows_duplicated: int
    rows_rejected: int
    rejection_reasons: Dict[str, int] = {}
    ignored_columns: List[str] = []
    total_rows_in_dataset: int


class TrainingRunOut(BaseModel):
    id: int
    status: str = Field(..., description="pending | running | succeeded | failed")
    total_rows: Optional[int] = None
    promoted: Optional[bool] = None
    resulting_version: Optional[str] = None
    message: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None


class Health(BaseModel):
    status: str
    active_model: Optional[str] = None
    movies_in_database: int
