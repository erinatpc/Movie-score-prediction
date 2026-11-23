# Día 2 — Informe EDA y calidad de datos

Dataset: `movies.csv`, **7668 filas × 15 columnas** (el enunciado hablaba de ~7.512; el archivo real tiene 7668).

## 1. Valores faltantes

|          |   nulos |     % |
|:---------|--------:|------:|
| budget   |    2171 | 28.31 |
| gross    |     189 |  2.46 |
| rating   |      77 |  1    |
| company  |      17 |  0.22 |
| runtime  |       4 |  0.05 |
| score    |       3 |  0.04 |
| votes    |       3 |  0.04 |
| country  |       3 |  0.04 |
| writer   |       3 |  0.04 |
| released |       2 |  0.03 |
| star     |       1 |  0.01 |
| year     |       0 |  0    |
| genre    |       0 |  0    |
| name     |       0 |  0    |
| director |       0 |  0    |

**Hallazgo clave:** `budget` falta en el **28.3%** de las filas. No es aleatorio: depende de la época (más nulos en los 80 y en los años recientes).

Nulos de `budget` por década (%):

|                |   1980 |   1990 |   2000 |   2010 |   2020 |
|:---------------|-------:|-------:|-------:|-------:|-------:|
| % nulos budget |   43.5 |   30.9 |   17.3 |     24 |     40 |

- Score medio con budget conocido: 6.386 | con budget nulo: 6.402 → el faltante casi no informa el score, pero se conserva el indicador `budget_missing` y se comprueba en CV.

- Mecanismo probable: **MAR** (depende de año y país/estudio, observables). Se imputa con mediana por género y año, y se compara contra KNN e Iterative en el día 3.

- `score` tiene 3 nulos (películas de 2020 sin votos): se **eliminan** del entrenamiento.

## 2. Variable objetivo: `score`

|       |   count |   mean |   std |   min |   25% |   50% |   75% |   max |
|:------|--------:|-------:|------:|------:|------:|------:|------:|------:|
| score |    7665 |   6.39 | 0.969 |   1.9 |   5.8 |   6.5 |   7.1 |   9.3 |

- Desviación estándar **0.969**; el 50% central está entre 5.8 y 7.1.

- MAE de predecir la media en todo el dataset: **0.756** (piso de referencia).

## 3. Cobertura temporal y split

- Años 1980–2020; el dataset contiene ~200 películas por año (1980–83 y 2020 tienen menos).

- Split temporal: **train ≤ 2016: 7043 filas** | **test 2017–2020: 625 filas** (3 sin score).

- Score medio train 6.385 vs test 6.452; MAE baseline en test (predecir media del train): **0.732**.

## 4. Variables categóricas y cardinalidad

| columna   |   únicos |   aparecen 1 sola vez |   % filas con valor raro (≤2 apariciones) | más frecuente      |
|:----------|---------:|----------------------:|------------------------------------------:|:-------------------|
| director  |     2949 |                  1558 |                                      33.3 | Woody Allen        |
| writer    |     4535 |                  3127 |                                      59.6 | Woody Allen        |
| star      |     2814 |                  1771 |                                      32.5 | Nicolas Cage       |
| company   |     2385 |                  1695 |                                      29.9 | Universal Pictures |
| country   |       59 |                    11 |                                       0.4 | United States      |
| genre     |       19 |                     3 |                                       0.1 | Comedy             |
| rating    |       12 |                     2 |                                       0   | R                  |

- `director`, `writer`, `star` y `company` tienen miles de valores y más de la mitad aparece una sola vez: **one-hot es inviable** → se usan features de historial previo (día 3).

- `director` contiene el valor basura `Directors` en 28 filas → se trata como nulo.

- `genre` está muy concentrado (Comedy/Action/Drama ≈ 71%); `country` ≈ 71% Estados Unidos; `rating` agrupa 12 valores, varios casi vacíos.

## 5. Variables numéricas

|       |   year |   runtime |         budget |
|:------|-------:|----------:|---------------:|
| count | 7668   |    7664   | 5497           |
| mean  | 2000.4 |     107.3 |    3.55899e+07 |
| std   |   11.2 |      18.6 |    4.14573e+07 |
| min   | 1980   |      55   | 3000           |
| 25%   | 1991   |      95   |    1e+07       |
| 50%   | 2000   |     104   |    2.05e+07    |
| 75%   | 2010   |     116   |    4.5e+07     |
| max   | 2020   |     366   |    3.56e+08    |

- `budget` muy asimétrico (asimetría 2.5 → -1.2 tras `log1p`) → se usa `log_budget`.

- `runtime`: mediana 104 min; máximo 366 (atípico real, no error).

## 6. Correlación con el score (Spearman) y fuga de información

|         |   ρ con score |
|:--------|--------------:|
| votes   |         0.428 |
| runtime |         0.4   |
| gross   |         0.126 |
| year    |         0.099 |
| budget  |        -0.001 |

- `votes` (ρ≈0,43) y `gross` solo existen **después del estreno** → quedan excluidos. `runtime` (ρ≈0,40) sí es legítima: se conoce antes de producir.

## 7. Score por género (9 más frecuentes)

| genre     |   count |   mean |
|:----------|--------:|-------:|
| Comedy    |    2245 |  6.194 |
| Action    |    1704 |  6.203 |
| Drama     |    1516 |  6.694 |
| Crime     |     551 |  6.672 |
| Biography |     443 |  7.031 |
| Adventure |     427 |  6.292 |
| Animation |     338 |  6.769 |
| Horror    |     322 |  5.751 |
| Fantasy   |      44 |  6.007 |

## 8. Chequeos de calidad

- Filas duplicadas: **0**.

- Filas donde el año de `released` difiere de `year`: 1356 (estreno en otro país/año) → de `released` solo se usa el **mes**.

- `budget` ≤ 0: 0.

## 9. Respuestas a las preguntas abiertas del día 1

1. Nulos: budget 28.3%, gross 2.5%, rating 1.0%, runtime 0.05%.

2. Desviación estándar del score 0.969; MAE del baseline en test 0.732.

3. Test 2017–2020: 625 filas (622 con score); suficientes para una estimación estable.

4. Directores que aparecen una sola vez: 1558 de 2949.

5. Duplicados: 0. Presupuestos: no hay indicador de moneda; se asumen nominales en USD.

6. Los umbrales del día 1 se confirman con un ajuste (ver `docs/01_business_understanding.md`, sección 6).
