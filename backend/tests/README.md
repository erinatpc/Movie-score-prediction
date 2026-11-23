# Pruebas

- `test_core.py`, `test_handlers.py`: lógica del servicio y manejadores. No requieren FastAPI.
- `test_api.py`: pruebas HTTP de la API real (requieren `fastapi` y `httpx`; se omiten si no están instalados).

Herramientas para entornos **sin** FastAPI (no forman parte del producto):
- `_fastapi_stub.py`: sustituto mínimo de FastAPI para poder importar y probar `app/main.py`.
- `harness_server.py`: servidor de prueba (Flask) con las mismas rutas, usado para verificar la web en un navegador.
- `gen_openapi_offline.py`: genera `docs/openapi.json` a partir de las rutas y modelos. Con FastAPI instalado, usar `python -m app.export_openapi`.
