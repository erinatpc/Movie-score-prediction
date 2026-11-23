# Día 5 — Tuning, evaluación en test ciego y Model Card

## 1. Tuning y ensamble (CV temporal sobre train ≤ 2016)

Búsqueda aleatoria (12 combinaciones por modelo) optimizando MAE. Mejores hiperparámetros:

- `random_forest`: `{'n_estimators': 200, 'min_samples_leaf': 3, 'max_features': 0.2, 'max_depth': 20}`

- `extra_trees`: `{'n_estimators': 200, 'min_samples_leaf': 3, 'max_features': 0.5, 'max_depth': 20}`

- `hist_gb`: `{'min_samples_leaf': 20, 'max_leaf_nodes': 15, 'max_iter': 200, 'learning_rate': 0.03, 'l2_regularization': 0.0}`


| modelo                        |    MAE |   MAE std |   RMSE |      R² |   mejora vs baseline |
|:------------------------------|-------:|----------:|-------:|--------:|---------------------:|
| ensamble (promedio RF+ET+HGB) | 0.5753 |    0.0373 | 0.7527 |  0.3817 |               0.2446 |
| random_forest (tuneado)       | 0.5803 |    0.0389 | 0.7576 |  0.3739 |               0.2381 |
| hist_gb (tuneado)             | 0.5827 |    0.0394 | 0.7606 |  0.3681 |               0.235  |
| extra_trees (tuneado)         | 0.5847 |    0.0366 | 0.7657 |  0.3602 |               0.2323 |
| media (baseline)              | 0.7617 |    0.0619 | 0.9697 | -0.0259 |               0      |

**Modelo elegido (solo con CV): ensamble (promedio RF+ET+HGB).** Regla: el ensamble se elige solo si mejora ≥ 0,003 de MAE al mejor modelo simple.

## 2. Evaluación ÚNICA en el test ciego (2017–2020)

El test se evaluó una sola vez, después de fijar el modelo. n = 622 películas.

| modelo                        |    MAE |   RMSE |      R² |
|:------------------------------|-------:|-------:|--------:|
| ensamble (promedio RF+ET+HGB) | 0.6184 | 0.8492 |  0.1884 |
| baseline (media del train)    | 0.7317 | 0.945  | -0.005  |

- Mejora de MAE vs baseline: **15.5%** (IC 95% bootstrap: 11.2% a 19.9%).

- IC 95% del MAE del modelo: [0.573, 0.662].

- Prueba de Wilcoxon pareada sobre errores absolutos (H1: el modelo es mejor): p = 3.79e-09.

### Criterios de aceptación (definidos en el día 1)

- ✅ MAE ≤ 0.65
- ✅ Mejora ≥ 10% vs baseline
- ❌ R² ≥ 0.30
- ✅ R² ≤ 0.80 (sin sospecha de leakage)
- ✅ CV estable (std MAE entre folds < 0,06)

**Resultado: modelo NO cumple todos los criterios.**

## 3. Importancia por permutación (test, descriptivo)

| variable       |   aumento de MAE al permutar |
|:---------------|-----------------------------:|
| runtime        |                       0.0763 |
| genre          |                       0.034  |
| director       |                       0.0128 |
| star           |                       0.0084 |
| country        |                       0.0072 |
| log_budget     |                       0.0065 |
| writer         |                       0.0042 |
| budget_missing |                       0.0025 |
| company        |                       0.0024 |
| release_month  |                       0.0003 |
| rating         |                       0      |
| year           |                       0      |

## 4. Error por subgrupo

|                        |   n |   MAE |
|:-----------------------|----:|------:|
| director con historial | 343 | 0.562 |
| director nuevo         | 279 | 0.688 |
| EE.UU.                 | 378 | 0.599 |
| Otros                  | 244 | 0.648 |

Si el MAE de directores nuevos es mayor, el modelo es menos fiable con talento sin historial: debe mostrarse en la app.

## 5. Diagnóstico: ¿por qué el R² del test (0,19) es menor que el del CV (0,38)?

Análisis posterior, solo descriptivo; no se usó para elegir ni ajustar el modelo.

|   año |   n |   std score |   MAE |   MAE baseline |     R² |
|------:|----:|------------:|------:|---------------:|-------:|
|  2017 | 200 |       0.874 | 0.596 |          0.704 |  0.228 |
|  2018 | 200 |       0.885 | 0.531 |          0.705 |  0.353 |
|  2019 | 200 |       1.02  | 0.702 |          0.769 |  0.029 |
|  2020 |  22 |       1.164 | 0.852 |          0.9   | -0.032 |

- La dispersión del score es parecida (desv. est. train 0.971 vs test 0.943), así que no explica la brecha.

- Directores sin historial en el train: **45%** de las películas de test frente a 39% de media en los folds de CV. En test el historial se congela en 2016 (una película de 2020 no "ve" las de 2017–2019), lo que hace la evaluación más exigente.

- El rendimiento cambia mucho entre años (R² alto en 2018, casi nulo en 2019) con solo ~200 películas por año: el R² del test es una estimación ruidosa. Con estos datos la brecha no queda explicada del todo; es una limitación a reportar, no a ocultar.
