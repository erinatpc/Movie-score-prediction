"""API REST del servicio de IA (FastAPI). Documentación interactiva en /docs; contrato en /openapi.json."""
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import bootstrap, config, schemas, service, trainer


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap.bootstrap()
    yield


app = FastAPI(
    title="Movie Score API",
    version="1.0.0",
    description=(
        "Servicio de IA que **predice el score de una película usando solo datos de pre-producción**, guarda el "
        "historial de predicciones, expone las métricas del modelo y permite **reentrenarlo** con datos nuevos.\n\n"
        "Flujo: `POST /training-file` (sube películas nuevas con su score real) → `POST /retrain` → "
        "`GET /retrain/{id}` (estado) → `GET /metrics` (comparar versiones)."),
    openapi_tags=[
        {"name": "Predicción", "description": "Enviar datos al modelo y obtener el resultado"},
        {"name": "Historial", "description": "Predicciones previas: datos enviados y resultado"},
        {"name": "Métricas", "description": "Rendimiento del modelo y de sus versiones"},
        {"name": "Reentrenamiento", "description": "Subir datos y reentrenar el modelo"},
        {"name": "Sistema", "description": "Estado del servicio y datos auxiliares"},
    ],
    lifespan=lifespan,
)

# CORS: solo el navegador (frontend) llama al backend desde otro origen. Orígenes configurables por entorno.
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(service.ServiceError)
async def service_error_handler(request, exc: service.ServiceError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


@app.get("/health", response_model=schemas.Health, tags=["Sistema"], summary="Estado del servicio")
def health():
    return service.health()


@app.get("/options", response_model=schemas.Options, tags=["Sistema"],
         summary="Valores frecuentes para los formularios (géneros, clasificaciones, países, meses)")
def options():
    return service.options()


@app.get("/dataset", response_model=schemas.DatasetSummary, tags=["Reentrenamiento"],
         summary="Resumen de los datos de entrenamiento almacenados")
def dataset():
    return service.dataset()


@app.post("/predict", response_model=schemas.PredictResponse, tags=["Predicción"],
          summary="Predecir el score de una película")
def predict(request: schemas.PredictRequest):
    """Recibe los datos **conocidos antes de producir** la película y devuelve el score estimado (0-10).
    La predicción queda guardada en el historial."""
    return service.predict(request)


@app.get("/predictions", response_model=schemas.PredictionsPage, tags=["Historial"],
         summary="Historial de predicciones (más recientes primero)")
def predictions(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    return service.predictions(limit, offset)


@app.get("/models", response_model=List[schemas.ModelVersionOut], tags=["Métricas"],
         summary="Versiones del modelo con sus métricas")
def models():
    return service.models_list()


@app.get("/metrics", response_model=schemas.MetricsResponse, tags=["Métricas"],
         summary="Métricas de rendimiento del modelo activo (o de una versión) y su historial")
def metrics(version: Optional[str] = Query(None, description="Versión (ej. v1). Por defecto, la activa.")):
    return service.metrics(version)


@app.post("/training-file", response_model=schemas.UploadResponse, tags=["Reentrenamiento"],
          summary="Enviar el archivo CSV de entrenamiento")
async def training_file(file: UploadFile = File(..., description="CSV con películas y su score real")):
    """Columnas obligatorias: `year`, `score`, `genre`. Opcionales: name, director, writer, star, company, rating,
    country, budget, runtime, released (o release_month). `votes` y `gross` se ignoran (se conocen tras el estreno).
    Las películas ya existentes (mismo título y año) se omiten."""
    content = bytearray()
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > max_bytes:
            raise service.TooLarge(f"El archivo supera el máximo de {config.MAX_UPLOAD_MB} MB")
    return service.upload_training_file(file.filename or "upload.csv", bytes(content))


@app.post("/retrain", response_model=schemas.TrainingRunOut, status_code=202, tags=["Reentrenamiento"],
          summary="Solicitar el reentrenamiento del modelo")
def retrain(background_tasks: BackgroundTasks):
    """Lanza el reentrenamiento en segundo plano con todos los datos almacenados. El candidato se compara con el
    modelo activo sobre las películas más recientes y solo se promueve si lo mejora. Consulte el estado en
    `GET /retrain/{id}`."""
    run = service.start_retrain()
    background_tasks.add_task(trainer.run_retrain, run["id"])
    return run


@app.get("/retrain", response_model=List[schemas.TrainingRunOut], tags=["Reentrenamiento"],
         summary="Últimos reentrenamientos")
def retrain_list():
    return service.retrain_list()


@app.get("/retrain/{run_id}", response_model=schemas.TrainingRunOut, tags=["Reentrenamiento"],
         summary="Estado de un reentrenamiento")
def retrain_status(run_id: int):
    return service.retrain_status(run_id)
