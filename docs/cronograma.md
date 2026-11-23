# Cronograma de trabajo — CRISP-ML(Q)

Proyecto: predicción del score de películas con servicio de IA (API REST), base de datos y cliente web.
Duración: **2 semanas (10 días hábiles)**, con los fines de semana como colchón para imprevistos.

Cada fase de CRISP-ML(Q) incluye su propio control de calidad (QA): datos, código, modelo y despliegue.

## Semana 1 — Datos y modelo (fases 1 a 4)

| Día | Fase CRISP-ML(Q) | Actividades | Entregable | QA de la fase |
|---|---|---|---|---|
| 1 | 1. Business & Data Understanding | Definir problema, variable objetivo, métricas y umbral de aceptación; lista de variables permitidas y prohibidas (fuga de datos); riesgos | ML Canvas, catálogo de métricas (`docs/01_business_understanding.md`) | Revisar que ninguna variable posterior al estreno esté permitida |
| 2 | 1. Data Understanding | EDA: nulos, distribución del score, cardinalidad, correlaciones, calidad | Informe EDA, diccionario de datos | Duplicados, rangos, valores basura |
| 3 | 2. Data Engineering | Split temporal antes de imputar; comparación de imputación de `budget`; variables de historial previo sin fuga; pipeline de scikit-learn | Pipeline reproducible | Test de ausencia de columnas prohibidas; cero nulos tras el pipeline |
| 4 | 3. ML Model Engineering | Baseline y 5 modelos con CV temporal; análisis de errores; diseño de la BD y de la API | Shortlist de modelos, esquema SQL, contrato API | CV sin fuga; semillas fijas |
| 5 | 3 y 4. Modelo y Evaluación | Tuning, ensamble, evaluación única en test ciego, Model Card, serialización | Modelo v1, Model Card | Test usado una sola vez; IC por bootstrap; criterios de aceptación |

**Hito 1:** modelo elegido, evaluado en test ciego y documentado.

## Semana 2 — Servicio, reentrenamiento, web y entrega (fases 4 a 6)

| Día | Fase CRISP-ML(Q) | Actividades | Entregable | QA de la fase |
|---|---|---|---|---|
| 6 | 5. Deployment | Servicio FastAPI: `/predict`, historial, métricas; base de datos SQLite; `ml_core.py` compartido con el notebook | Servicio con predicción e historial | Tests de la lógica del servicio |
| 7 | 5 y 6. Deployment y Maintenance | Subida de CSV (`/training-file`), reentrenamiento en segundo plano (`/retrain`), versionado y promoción solo si mejora | Reentrenamiento funcional | Comparación en el mismo holdout; un solo modelo activo |
| 8 | 5. Deployment | Swagger / OpenAPI, CORS, validación de entradas y errores | `docs/openapi.json` | Códigos de error 404/409/413/422 |
| 9 | 5. Deployment | Cliente web que consulta todos los endpoints | `frontend/` | Prueba en navegador de todos los flujos |
| 10 | 4 y 6. QA y cierre | Pruebas de extremo a extremo, documentación, video, GitHub y Pull Requests | Entrega final | Revisión de PR (incluida revisión con IA) |

**Hito 2:** sistema integrado (modelo + API + BD + web) subido a GitHub, con Swagger y documentación.

## Qué quedó fuera del alcance (y por qué)
- **Monitoreo de drift y SHAP:** el plazo de dos semanas no permite añadirlos sin comprometer lo obligatorio. Quedan como trabajo futuro (ver `docs/model_card.md`).
- **Servicios de inferencia y entrenamiento separados, Docker Compose, PostgreSQL:** una sola aplicación de IA con tareas en segundo plano cubre los requisitos con menos riesgo. La separación se justificaría con reentrenamientos largos o mucha carga.
