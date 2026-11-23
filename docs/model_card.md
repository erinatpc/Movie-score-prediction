# Model Card — Movie Score v1

## Resumen
Regresor que estima el **score** de una película usando solo información disponible **antes de producirla**.
Ensamble promedio de Random Forest + Extra Trees + HistGradientBoosting (scikit-learn), con imputación de
presupuesto por mediana de género y año y variables de historial previo de director, guionista, estrella y productora.

## Uso previsto
- **Sí:** priorizar y comparar proyectos en pre-producción; apoyar (no reemplazar) decisiones de inversión.
- **No:** predecir el éxito comercial, evaluar personas, o usarse con datos posteriores al estreno.

## Datos
- `movies.csv`: 7.668 filas, 1980–2020; 7.665 con score.
- Entrenamiento: 7.043 películas (≤2016). Test ciego: 622 películas (2017–2020).
- **Excluidas por leakage o irrelevancia:** `votes`, `gross`, fecha exacta de `released`, `name`.
- Entradas: director, writer, star, company, genre, rating, country, release_month, year, runtime, log_budget, budget_missing.

## Entrenamiento y validación
- Split temporal + CV de 5 folds *forward-chaining* (valida con años posteriores al entrenamiento).
- Imputación, historial previo y encodings dentro del `Pipeline`: nada se ajusta con datos de validación o test.
- Semilla 42; versiones y metadatos en `models/model_v1_metadata.json`.
- Hiperparámetros: búsqueda aleatoria (12 combinaciones por modelo), ver `reports/05_tune_evaluate_report.md`.

## Rendimiento
| Conjunto | MAE | RMSE | R² |
|---|---|---|---|
| CV temporal (train) | 0,575 | 0,753 | 0,382 |
| **Test ciego 2017–2020** | **0,618** | **0,849** | **0,188** |
| Baseline (media), test | 0,732 | 0,945 | −0,005 |

- Mejora de MAE sobre el baseline en test: **15,5 %** (IC 95 %: 11,2 %–19,9 %).
- Criterios de aceptación del día 1: cumple MAE ≤ 0,65, mejora ≥ 10 %, ausencia de señales de leakage y estabilidad en CV. **No cumple R² ≥ 0,30 en el test (0,188).**
- El R² del test varía mucho por año (≈0,35 en 2018, ≈0,03 en 2019): es una estimación ruidosa con ~200 películas por año.

## Variables más influyentes (permutación, test)
`runtime` ≫ `genre` > `director` > `star` > `country` > `log_budget`.

## Limitaciones
- Solo metadatos: no puede anticipar fracasos extremos (los mayores errores son películas con score < 3,5 que el modelo sobrestima).
- **Menos fiable con directores sin historial:** MAE 0,688 frente a 0,562 con historial. La API debe devolver `known_director` y la app debe mostrarlo.
- Error algo mayor fuera de EE.UU. (0,648 vs 0,599).
- Presupuestos nominales sin ajuste por inflación ni moneda; 28 % imputados.
- El score depende de la plataforma de votos: puede reflejar sesgos de ese público.

## Sesgos y consideraciones éticas
El modelo favorece a nombres con historial alto (efecto "bola de nieve"): puede penalizar a talento nuevo. Debe usarse como una referencia más, no como filtro automático.

## Despliegue y mantenimiento
- Servido por la API del proyecto (`backend/`): `POST /predict` devuelve el score, la versión del modelo y avisos (`known_director`, presupuesto imputado, año fuera de rango).
- Reentrenamiento con `POST /retrain` (datos de la base de datos, incluidos los archivos subidos con `POST /training-file`): el candidato se compara con el modelo activo sobre las películas más recientes y solo se promueve si lo mejora. Cada versión guarda sus métricas y el MAE de la versión anterior sobre el mismo conjunto.
- **No implementado (trabajo futuro):** monitoreo de data drift y concept drift, explicabilidad con SHAP, reentrenamiento programado y autenticación de la API.
