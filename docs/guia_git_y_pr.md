# Guía: ramas de GitHub, Pull Requests y revisión con IA

## Estrategia de ramas
`main` (versión estable) ← `develop` (integración) ← ramas de trabajo `feature/*` y `docs/*`. Cada rama termina en un Pull Request hacia `develop`;
al final, `develop` se fusiona en `main`.

| Rama | Contenido | Archivos |
|---|---|---|
| `docs/business-understanding` | Fase 1 y cronograma | `docs/01_business_understanding.md`, `docs/cronograma.md` |
| `feature/eda-and-data-pipeline` | EDA, imputación y pipeline | `docs/crisp-ml/`, `docs/data_dictionary.md`, `backend/ml_core.py` |
| `feature/model-training` | Notebook, modelo y Model Card | `notebooks/`, `backend/models/`, `docs/model_card.md`, `data/movies.csv` |
| `feature/backend-api` | Servicio FastAPI y base de datos | `backend/app/`, `backend/db/`, `backend/requirements.txt`, `backend/tests/`, `docs/database/`, `docs/openapi.json` |
| `feature/frontend` | Cliente web | `frontend/` |
| `docs/final-delivery` | README, documento CRISP-ML(Q), guion | `README.md`, `docs/CRISP-ML-Q_y_desarrollo.md`, `docs/guion_video.md`, `docs/architecture.*`, `.github/`, `.gitignore`, `data/demo_*.csv` |

## Comandos (desde la raíz del repositorio)
```bash
git init -b main && git add .gitignore README.md && git commit -m "chore: estructura inicial"
git remote add origin https://github.com/<usuario>/<repo>.git
git push -u origin main
git checkout -b develop && git push -u origin develop

# Repetir para cada rama de la tabla (ejemplo con la primera):
git checkout -b docs/business-understanding develop
git add docs/01_business_understanding.md docs/cronograma.md
git commit -m "docs: fase 1 de CRISP-ML(Q) y cronograma"
git push -u origin docs/business-understanding
```
Después, en GitHub: **New pull request** → base `develop` → compara con la rama → crear. Haz el *merge* de cada PR en orden y, al final, abre un PR de `develop` a `main`.

Consejo: si prefieres el repositorio en GitHub desde el principio, crea el repositorio vacío como **público** (la consigna pide la URL pública).

## Evidencia de revisión de PR con IA (punto extra)
1. Abre un PR con un cambio real (por ejemplo, `feature/backend-api`) y rellena la plantilla (`.github/pull_request_template.md`).
2. Pide la revisión a una IA y guarda la evidencia (captura con el nombre del revisor y sus comentarios):
   - **GitHub Copilot:** en el PR, *Reviewers* → *Copilot* (si tu cuenta lo tiene habilitado).
   - **Claude Code:** en una terminal dentro del repositorio, pedir «revisa este Pull Request» o ejecutar `/review`.
   - **Otro:** pegar el *diff* del PR (`git diff develop...<rama>`) en el asistente que uses y pedir una revisión de errores, seguridad y claridad.
3. Responde a los comentarios del revisor (aplica o justifica cada punto) y deja la conversación visible en el PR.
4. Incluye en el documento final una captura del PR con la revisión.

Qué pedir a la IA: errores de lógica, validación de entradas, manejo de errores, seguridad (CORS, subida de archivos), fuga de datos en el pipeline y claridad de la documentación.
