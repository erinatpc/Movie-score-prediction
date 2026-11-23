# Diccionario de datos — `movies.csv`

7.668 filas × 15 columnas (7.665 con `score`). Un registro = una película (~200 por año, 1980–2020).

| Columna | Tipo | ¿Entra al modelo? | Descripción | Nulos | Notas |
|---|---|---|---|---|---|
| `name` | texto | ❌ | Título | 0% | Identificador, sin poder predictivo |
| `rating` | categórica | ✅ | Clasificación por edades (R, PG-13, PG, G…) | 1,0% | 12 valores; raros se agrupan |
| `genre` | categórica | ✅ | Género principal | 0% | 19 valores; 71% Comedy/Action/Drama |
| `year` | entero | ✅ | Año de estreno | 0% | Define el split temporal |
| `released` | texto | ⚠️ solo el mes | Fecha y país de estreno | 0,03% | Año distinto a `year` en 1.356 filas; solo se usa el mes |
| **`score`** | decimal | 🎯 **objetivo** | Calificación (≈1,9–9,3) | 0,04% | Media 6,39, desv. 0,97. Se eliminan 3 filas sin score |
| `votes` | decimal | ❌ **leakage** | Nº de votos | 0,04% | Solo existe tras el estreno |
| `director` | categórica | ✅ (vía historial) | Director | 0% | 2.949 únicos; `Directors` (28 filas) = basura → nulo |
| `writer` | categórica | ✅ (vía historial) | Guionista | 0,04% | 4.535 únicos |
| `star` | categórica | ✅ (vía historial) | Estrella principal | 0,01% | 2.814 únicos |
| `country` | categórica | ✅ | País | 0,04% | 59 valores; ~71% EE.UU. |
| `budget` | decimal | ✅ (`log_budget`) | Presupuesto (USD nominal asumido) | **28,3%** | Muy asimétrico; se imputa por género y año |
| `gross` | decimal | ❌ **leakage** | Recaudación | 2,5% | Solo existe tras el estreno |
| `company` | categórica | ✅ (vía historial) | Productora | 0,22% | 2.385 únicos |
| `runtime` | decimal | ✅ | Duración (min) | 0,05% | Mediana 104; máx. 366 (real) |

## Variables derivadas

| Variable | Cómo se calcula |
|---|---|
| `log_budget` | `log1p(budget)`; nulos imputados con la mediana por género y bloque de 5 años |
| `budget_missing` | 1 si `budget` era nulo |
| `release_month` | Mes extraído de `released` |
| `<entidad>_prev_n` | `log1p` de nº de películas **de años anteriores** del director / guionista / estrella / productora |
| `<entidad>_prev_mean` | Score medio suavizado (k=5) de esas películas previas; media global si no hay historial |

## Casos límite acordados
- Director, guionista, estrella o productora desconocidos → `prev_n = 0` y `prev_mean = media global` (nunca error).
- `budget` ausente en la API → se imputa igual que en el entrenamiento.
- Cualquier entrada con `votes`, `gross` o `name` se ignora: no forman parte del contrato de la API.
