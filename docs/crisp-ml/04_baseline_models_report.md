# Día 4 — Modelado rápido: shortlist de modelos

Todos con el mismo preprocesamiento (imputación `genre_year`, historial previo, one-hot con categorías raras agrupadas), hiperparámetros por defecto razonables y **CV temporal de 5 folds** sobre el train (≤2016). El test ciego no se usa.

| modelo           |    MAE |   MAE std |   RMSE |      R² |   seg |   mejora vs baseline |
|:-----------------|-------:|----------:|-------:|--------:|------:|---------------------:|
| random_forest    | 0.5833 |    0.0348 | 0.7628 |  0.3642 |  11   |               0.2341 |
| extra_trees      | 0.5839 |    0.0376 | 0.764  |  0.3632 |   9   |               0.2334 |
| hist_gb          | 0.5881 |    0.0436 | 0.7671 |  0.3565 |   5.3 |               0.2279 |
| ridge            | 0.6051 |    0.0372 | 0.7863 |  0.3239 |   2.3 |               0.2055 |
| media (baseline) | 0.7617 |    0.0619 | 0.9697 | -0.0259 |   2.3 |               0      |

> **Nota:** CatBoost y LightGBM no estaban instalados en este entorno y no se pudieron instalar (sin acceso a red). `HistGradientBoostingRegressor` de scikit-learn es el equivalente directo de LightGBM (boosting por histogramas) y se usa como representante. Si los tienes, se pueden añadir a `MODELS` sin tocar el resto del pipeline.

## Shortlist para tuning (día 5)

Criterio: menor MAE en CV temporal, interpretabilidad y coste.

- **random_forest** — MAE 0.583 (±0.035), R² 0.364, mejora 23.4% vs baseline.

- **extra_trees** — MAE 0.584 (±0.038), R² 0.363, mejora 23.3% vs baseline.

- **hist_gb** — MAE 0.588 (±0.044), R² 0.357, mejora 22.8% vs baseline.

- **ridge** se conserva como referencia interpretable aunque no sea el mejor.


La diferencia de MAE entre los 3 primeros es 0.005, menor que la desviación entre folds (0.043): **no hay un ganador estadístico claro todavía**; el tuning y el ensamble del día 5 deciden.

## Análisis de errores (random_forest, predicciones fuera de muestra)

**Género (≥100 películas)**

| genre     |    n |   MAE |   sesgo |
|:----------|-----:|------:|--------:|
| Animation |  221 | 0.648 |   0.197 |
| Horror    |  166 | 0.64  |  -0.207 |
| Adventure |  200 | 0.616 |   0.032 |
| Comedy    | 1100 | 0.593 |  -0.022 |
| Action    |  954 | 0.59  |  -0.02  |
| Drama     |  783 | 0.574 |   0.067 |
| Crime     |  293 | 0.513 |   0.082 |
| Biography |  243 | 0.501 |   0.255 |

**¿Budget conocido?**

| budget_conocido   |    n |   MAE |   sesgo |
|:------------------|-----:|------:|--------:|
| sí                | 3243 | 0.587 |   0.021 |
| no                |  757 | 0.567 |   0.062 |

**Por quinquenio**

|   periodo |    n |   MAE |   sesgo |
|----------:|-----:|------:|--------:|
|      1995 |  600 | 0.624 |   0.078 |
|      2000 | 1000 | 0.612 |  -0.006 |
|      2005 | 1000 | 0.583 |   0.04  |
|      2010 | 1000 | 0.543 |   0.036 |
|      2015 |  400 | 0.553 |  -0.007 |

**Mayores errores (subestimó/sobrestimó)**

| name                         |   year | genre   |   score |   pred |
|:-----------------------------|-------:|:--------|--------:|-------:|
| Glitter                      |   2001 | Drama   |     2.3 |   6.48 |
| Gigli                        |   2003 | Comedy  |     2.5 |   6.63 |
| House of the Dead            |   2003 | Action  |     2.1 |   6.19 |
| The Hottie & the Nottie      |   2008 | Comedy  |     1.9 |   5.46 |
| Battlefield Earth            |   2000 | Action  |     2.5 |   5.98 |
| Superbabies: Baby Geniuses 2 |   2004 | Comedy  |     1.9 |   5.37 |
| Rollerball                   |   2002 | Action  |     3.1 |   6.4  |
| From Justin to Kelly         |   2003 | Comedy  |     2.1 |   5.4  |

Lectura: los mayores errores son **fracasos extremos** (score < 3,5) que el modelo sobrestima: con solo metadatos de pre-producción no hay señal para anticipar una película excepcionalmente mala.
