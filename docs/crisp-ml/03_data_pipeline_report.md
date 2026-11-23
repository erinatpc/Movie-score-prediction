# Día 3 — Data Engineering: split, imputación y pipeline

## 1. Split temporal (antes de imputar)

- Train (≤2016): **7043** filas · Test ciego (2017–2020): **622** filas (no se toca hasta el día 5).

- CV temporal de 5 folds (forward-chaining): fold 1: train 3043 → val 800, fold 2: train 3843 → val 800, fold 3: train 4643 → val 800, fold 4: train 5443 → val 800, fold 5: train 6243 → val 800.

- Imputación, encodings e historial se **ajustan solo con el train de cada fold** (dentro del `Pipeline`).

## 2. Comparación de imputación de `budget` (enmascarando valores conocidos)

Se oculta aleatoriamente el 25% de los presupuestos conocidos del train y se mide el error al recuperarlos (RMSE sobre `log_budget`; menor es mejor). Se ajusta con el 75% restante.

| método                    |   RMSE log_budget |   MAE log_budget |
|:--------------------------|------------------:|-----------------:|
| Iterative (+género, país) |             1.098 |            0.781 |
| Mediana por género y año  |             1.193 |            0.809 |
| KNN (k=10)                |             1.261 |            0.912 |
| Mediana global            |             1.367 |            0.976 |

## 3. Efecto de la imputación en el modelo (CV temporal, HistGradientBoosting)

| imputación   |    MAE |   MAE std folds |   RMSE |     R² |
|:-------------|-------:|----------------:|-------:|-------:|
| knn          | 0.5853 |          0.0429 | 0.7651 | 0.3602 |
| iterative    | 0.5876 |          0.0457 | 0.7655 | 0.3599 |
| native       | 0.5876 |          0.0436 | 0.7656 | 0.3593 |
| genre_year   | 0.5881 |          0.0436 | 0.7671 | 0.3565 |
| median       | 0.5902 |          0.0479 | 0.7695 | 0.3529 |

Diferencia máxima de MAE entre métodos: **0.0049**; desviación media entre folds: **0.0447**. Las diferencias son menores que el ruido entre folds, es decir, **no son significativas**.

**Decisión: `genre_year` (mediana de `log_budget` por género y bloque de 5 años).** Es casi tan buena como las demás en CV, supera a KNN y a la mediana global al recuperar valores enmascarados, es determinista, rápida, fácil de explicar y de reproducir en la API. Se conservan `iterative` y `native` como alternativas documentadas.

## 4. ¿Aporta el indicador `budget_missing`?

- Con indicador: MAE 0.5881 · Sin indicador: MAE 0.5887 (diferencia +0.0006, frente a una desviación entre folds de 0.0436).

- Se conserva el indicador: es gratuito y permite al modelo distinguir presupuestos imputados de reales.

## 5. Demostración de leakage: por qué se excluyen `votes` y `gross`

| variables                          |   MAE |    R² |
|:-----------------------------------|------:|------:|
| Sin leakage (variables permitidas) | 0.661 | 0.185 |
| + votes                            | 0.533 | 0.429 |
| + votes + gross                    | 0.517 | 0.451 |

Con las mismas variables base, agregar `votes` sube el R² de 0.19 a 0.43 y baja el MAE de 0.66 a 0.53, pero `votes` solo existe tras el estreno: en producción ese modelo no podría usarse. Regla práctica: **si un R² parece demasiado bueno, hay leakage.**

## 6. Verificación automática

- Columnas prohibidas presentes en las entradas del modelo: **ninguna**.

- Features finales tras el preprocesamiento: **56** (ej.: director_prev_n, director_prev_mean, writer_prev_n, writer_prev_mean, star_prev_n, star_prev_mean…).

- Nulos restantes tras el pipeline: 0.

## 7. Directores nuevos (cold start)

- Predicción con director inexistente y star nulo: 6.48 (sin error; usa la media global).
