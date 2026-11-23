# Fase 1 — Business & Data Understanding (CRISP-ML(Q))

Proyecto: predicción del score de películas con reentrenamiento, API REST y app web.
Rama sugerida: `docs/business-understanding` → PR a `develop`.

> Los valores marcados con **(validar)** son propuestas iniciales. Se confirman o ajustan con el EDA (día 2).

---

## 1. Problema de negocio

Una empresa de contenido (estilo Netflix o Disney) quiere estimar la **calidad percibida (score)** de una película **antes de producirla**, para priorizar presupuesto y decidir qué proyectos financiar.

**Pregunta que responde el sistema:** dados los metadatos conocidos en pre-producción (director, guionista, estrella, género, presupuesto, etc.), ¿qué score se espera que tenga la película?

**Usuarios:** analistas de producción y decisores de inversión, a través de la app web.

## 2. Viabilidad: ¿por qué ML y no reglas simples?

- Una regla simple (ej. "promedio del género") ignora la interacción entre director, estrella, presupuesto y año.
- El baseline de **predecir la media** nos da el piso objetivo. ML solo se justifica si lo supera de forma clara en el test temporal.
- Si el modelo no supera el baseline por el margen definido en la sección 6, la conclusión honesta es que los metadatos de pre-producción no bastan. Eso también es un resultado válido.

## 3. Formulación de la tarea de ML

| Elemento | Definición |
|---|---|
| Tipo de problema | **Regresión supervisada** |
| Variable objetivo | `score` (continua, escala aprox. 0 a 10) |
| Unidad de predicción | Una película |
| Momento de predicción | Antes de la producción (solo información disponible entonces) |
| Dataset | `movies.csv`, 7.512 filas |
| Experimento secundario (opcional) | Clasificación: `score >= 7` sí/no |

## 4. Variables

### 4.1 Permitidas (disponibles en pre-producción)

| Variable | Tipo | Tratamiento previsto |
|---|---|---|
| `director`, `writer`, `star`, `company` | Categórica, alta cardinalidad | Target encoding suavizado dentro de cada fold, score histórico previo, agrupar raras en "otros" |
| `genre`, `rating`, `country` | Categórica, baja cardinalidad | One-hot o encoding nativo del modelo |
| `budget` | Numérica, muy asimétrica | Imputar con la mediana por género y año; crear `log_budget` |
| `runtime` | Numérica | Imputar con la mediana |
| `year` | Numérica | Usada también para el split temporal |
| `released` (solo el mes) | Fecha | Derivar `mes_estreno` |

### 4.2 Prohibidas (fuga de información / data leakage)

| Variable | Motivo de exclusión |
|---|---|
| `votes` | Solo existe después del estreno y está fuertemente correlacionada con el score |
| `gross` | La recaudación se conoce después del estreno |
| `released` (fecha exacta) | Se conoce tarde; se conserva solo el mes |
| `name` | Identificador sin poder predictivo |

> Regla del proyecto: ninguna variable prohibida puede entrar al modelo ni al endpoint `/predict`. Se verifica con un test automático (día 9).

## 5. Catálogo de métricas

### 5.1 Métricas de ML

| Métrica | Qué mide | Por qué se usa |
|---|---|---|
| **MAE** | Error medio absoluto, en puntos de score | Principal para negocio, fácil de explicar |
| **RMSE** | Error cuadrático medio, en puntos de score | Penaliza más los errores grandes |
| **R²** | Proporción de varianza explicada | Mide cuánto aporta el modelo frente a la media |
| **MAE/RMSE del baseline (media)** | Piso de referencia | Todo modelo se compara contra esto |
| **Mejora relativa vs. baseline** | `(MAE_base − MAE_modelo) / MAE_base` | Resume el valor real del modelo |

### 5.2 Métricas de negocio

| KPI | Definición | Cómo se mide en el proyecto |
|---|---|---|
| Utilidad de la estimación | El error es suficientemente pequeño para distinguir proyectos buenos de malos | MAE frente a la dispersión del score |
| Capacidad de priorizar | El modelo ordena bien las películas | Correlación de Spearman entre score real y predicho (opcional) |
| Confianza operativa | El sistema responde y se mantiene | Latencia de `/predict` y versión del modelo en uso |

## 6. Criterios de aceptación (validar)

El modelo se acepta si, en el **test temporal ciego (2017–2020)**, cumple todo lo siguiente:

1. **MAE ≤ 0,65** puntos de score.
2. **Mejora ≥ 10 %** en MAE respecto al baseline de la media.
3. **R² ≥ 0,30**.
4. **Sin señales de fuga:** si R² > 0,80, se revisa el pipeline antes de aceptar nada.
5. **Estabilidad:** la desviación del MAE entre folds de CV es razonable (no hay un fold muy distinto del resto).

> Ajustar estos umbrales tras ver la distribución real del score en el EDA. Si el score tiene muy poca varianza, el baseline ya será bueno y la exigencia relativa (criterio 2) pesa más que el MAE absoluto.

## 7. Estrategia de validación

- **Split temporal:** entrenamiento hasta 2016 y **test ciego** de 2017 a 2020. El test se usa **una sola vez**, al final.
- **CV de 5 folds** dentro del train, para comparar modelos y ajustar hiperparámetros.
- Imputación, encodings y features históricos se calculan **dentro del pipeline y de cada fold**.
- Los features históricos (score promedio del director o la estrella) usan **solo películas anteriores** a la película evaluada.

## 8. Requisitos de calidad de datos

| Dimensión | Requisito | Verificación |
|---|---|---|
| Completitud | Reportar el porcentaje de nulos por columna | EDA, día 2 |
| Representatividad | Distribución por año, género y país | EDA, día 2 |
| Actualidad | Rango de años cubierto; el test debe ser posterior al train | EDA, día 2 |
| Consistencia | Sin duplicados; tipos correctos; presupuestos en la misma moneda | EDA, día 2 |
| Cardinalidad | Contar valores únicos por categórica y frecuencia de los raros | EDA, día 2 |

## 9. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| **Data leakage** (`votes`, `gross`) | Métricas falsamente excelentes | Lista de variables prohibidas y test automático |
| **Sobreajuste** por alta cardinalidad | El modelo memoriza directores | Target encoding suavizado, CV, CatBoost |
| **Directores o estrellas nuevos** (cold start) | Error de predicción o fallo del endpoint | Valor por defecto (media global) y prueba específica |
| **Cambio temporal** (concept drift) | El modelo se degrada con los años | Split temporal, monitoreo de drift y reentrenamiento |
| **Sesgo hacia nombres consolidados** | Penaliza a talento nuevo | Documentarlo en la Model Card; revisar el error por subgrupos |
| **Score con poca varianza** | Difícil mejorar al baseline | Medir siempre la mejora relativa |
| **Privacidad** | Los datos son metadatos públicos de películas, riesgo bajo | Confirmar origen y licencia del dataset |
| **Expectativas irreales** | Frustración con un R² modesto | Expectativa documentada: R² de 0,3 a 0,5 sin `votes` |

## 10. ML Canvas

| Bloque | Contenido |
|---|---|
| **Propuesta de valor** | Estimar el score de una película en pre-producción para apoyar decisiones de inversión |
| **Decisión a apoyar** | Qué proyectos priorizar o revisar antes de comprometer presupuesto |
| **Tarea de ML** | Regresión del `score` |
| **Fuente de datos** | `movies.csv` (7.512 filas); nuevos CSV para reentrenar |
| **Features** | Variables permitidas de la sección 4.1 |
| **Etiqueta** | `score` |
| **Evaluación offline** | MAE, RMSE y R² en test temporal 2017–2020 frente al baseline de la media |
| **Predicción en producción** | `POST /predict` con las variables pre-producción; respuesta con el score y la versión del modelo |
| **Reentrenamiento** | `POST /retrain` con un CSV nuevo; nueva versión que se promueve solo si mejora |
| **Monitoreo** | Data drift en budget, género y year; métricas por versión guardadas en la BD |
| **Fallback** | Si falla el modelo, devolver la media del género y marcarlo en la respuesta |
| **Equipo y roles** | Ver sección 11 |

## 11. Roles (adaptados al equipo del proyecto)

| Rol en CRISP-ML(Q) | Responsabilidad en este proyecto | Entregable |
|---|---|---|
| Product Owner / Negocio | Validar métricas y umbrales | ML Canvas y criterios de aceptación |
| Experto de dominio | Revisar variables permitidas y casos límite | Diccionario de datos |
| Data Scientist | Pipeline, modelos y tuning | Shortlist y Model Card |
| Ingeniero MLOps / Software | API, BD, Docker y monitoreo | Endpoints y CI/CD |

> Si trabajas solo, una persona cubre los cuatro roles. Usa esta tabla como lista de verificación.

## 12. Alcance

**Dentro:** regresión del score, imputación de faltantes, selección del modelo, reentrenamiento, API REST con Swagger, métricas en BD, app web y ramas en GitHub.

**Fuera (si sobra tiempo):** clasificación `score >= 7`, SHAP, despliegue Canary o A/B, Human-in-the-Loop.

## 13. Preguntas abiertas para el EDA (día 2)

1. ¿Qué porcentaje de nulos tiene cada columna, en especial `budget`, `rating` y `runtime`?
2. ¿Cuál es la desviación estándar del score? ¿Qué MAE da el baseline de la media?
3. ¿Cuántas películas hay por año? ¿Son suficientes en 2017–2020 para un test estable?
4. ¿Cuántos directores, guionistas y estrellas aparecen una sola vez?
5. ¿Hay duplicados o presupuestos en monedas distintas?
6. ¿Cuánto cambian los umbrales de la sección 6 a la luz de las respuestas anteriores?
