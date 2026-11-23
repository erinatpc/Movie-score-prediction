# Guion del video demostrativo (5 minutos)

**Preparación (antes de grabar):** servicio en marcha (`uvicorn app.main:app --port 8000` dentro de `backend/`),
web abierta en `http://localhost:5500`, Swagger en `http://localhost:8000/docs`. Para empezar de cero, borra `backend/data/app.db`.
Ten a mano `data/demo_nuevas_peliculas_2017_2020.csv`.

| Tiempo | Qué mostrar | Qué decir |
|---|---|---|
| 0:00–0:30 | Pantalla de la web y `docs/architecture.png` | Qué problema resuelve (estimar el score de una película **antes de producirla**) y la arquitectura: notebook → servicio de IA → base de datos ← web por API REST. |
| 0:30–1:30 | `notebooks/modelo_peliculas.ipynb` (salidas ya guardadas) | CRISP-ML(Q) en 4 ideas: (1) variables de pre-producción, sin `votes` ni `gross` (fuga de datos); (2) split temporal y CV temporal; (3) imputación de `budget` comparada; (4) resultado honesto: MAE 0,62 (15,5 % mejor que el baseline) y R² 0,19. |
| 1:30–2:30 | Pestaña **Predicción** | «Rellenar ejemplo» → Predecir. Explicar el score, el aviso de director sin historial y la versión del modelo. Probar un director inexistente. |
| 2:30–3:00 | Pestaña **Historial** | Cada predicción queda guardada con los datos enviados y el resultado. |
| 3:00–3:30 | Pestaña **Métricas** | MAE/RMSE/R² frente al baseline, criterios de aceptación (el R² no llega a 0,30: decirlo) y versiones del modelo. |
| 3:30–4:30 | Pestaña **Datos y reentrenamiento** | Subir el CSV de demo → informe (se ignoran `votes`/`gross`). Reentrenar → estado en vivo → «Se promueve v2». Volver a Métricas: dos versiones, comparación con la anterior **sobre el mismo conjunto**. |
| 4:30–5:00 | `http://localhost:8000/docs` y GitHub | Swagger con los 5 endpoints requeridos, el diagrama de base de datos y el repositorio con sus ramas y Pull Requests. |

**Consejos:** no leer el código; mostrar resultados. Si el reentrenamiento tarda, aprovechar para explicar la regla de promoción
(solo se activa el candidato si supera al modelo actual en las películas más recientes).
