"""Genera docs/openapi.json SIN necesitar FastAPI, a partir de las mismas rutas y modelos de app/main.py.

Sirve para entornos donde FastAPI no está instalado. Con FastAPI instalado, el documento oficial se genera con:
    python -m app.export_openapi
y sustituye a este archivo (mismo contenido funcional, generado por el propio framework).
"""
import inspect
import json
import re
import sys
import typing
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(Path(__file__).parent)]
import _fastapi_stub  # noqa: E402

_fastapi_stub.install()
import fastapi  # noqa: E402
from pydantic import BaseModel, TypeAdapter  # noqa: E402

from app import config  # noqa: E402
from app import main as api_main  # noqa: E402

REF = "#/components/schemas/{model}"
PARAM_DOC = {"limit": "Máximo de elementos por página (1-500)", "offset": "Elementos a saltar",
             "version": "Versión del modelo (ej. v1). Por defecto, la activa.", "run_id": "Identificador del reentrenamiento"}
ERRORS = {("POST", "/predict"): {"503": "No hay modelo activo"},
          ("GET", "/metrics"): {"404": "La versión no existe o no hay modelo activo"},
          ("POST", "/retrain"): {"409": "Ya hay un reentrenamiento en curso", "503": "No hay modelo activo"},
          ("GET", "/retrain/{run_id}"): {"404": "No existe el reentrenamiento"},
          ("POST", "/training-file"): {"413": "El archivo supera el tamaño máximo",
                             "422": "CSV inválido (columnas obligatorias ausentes o sin filas válidas)"}}
schemas = {}


def schema_ref(tp):
    """Esquema JSON; los modelos pydantic van a components/schemas y se referencian con $ref (como hace FastAPI)."""
    if typing.get_origin(tp) is list:
        return {"type": "array", "items": schema_ref(typing.get_args(tp)[0])}
    js = tp.model_json_schema(ref_template=REF)
    schemas.update(js.pop("$defs", {}))
    schemas[tp.__name__] = js
    return {"$ref": REF.format(model=tp.__name__)}


def build():
    paths = {}
    for r in api_main.app.routes:
        h, sig = r["handler"], inspect.signature(r["handler"])
        op = {"tags": r.get("tags", []), "summary": r.get("summary", h.__name__),
              "description": inspect.cleandoc(h.__doc__ or ""), "operationId": f"{h.__name__}_{r['method'].lower()}",
              "parameters": [], "responses": {}}
        if not op["description"]:
            del op["description"]
        path = re.sub(r"\{(\w+)\}", r"{\1}", r["path"])
        for name, p in sig.parameters.items():
            ann = p.annotation
            if ann is fastapi.BackgroundTasks:
                continue
            if ann is fastapi.UploadFile:
                op["requestBody"] = {"required": True, "content": {"multipart/form-data": {"schema": {
                    "type": "object", "required": ["file"],
                    "properties": {"file": {"type": "string", "format": "binary",
                                            "description": "CSV con películas y su score real"}}}}}}
            elif inspect.isclass(ann) and issubclass(ann, BaseModel):
                op["requestBody"] = {"required": True, "content": {"application/json": {"schema": schema_ref(ann)}}}
            elif f"{{{name}}}" in r["path"]:
                op["parameters"].append({"name": name, "in": "path", "required": True,
                                         "schema": {"type": "integer"}, "description": PARAM_DOC.get(name)})
            else:
                base = typing.get_args(ann)[0] if typing.get_origin(ann) is typing.Union else ann
                sch = {"type": "integer" if base is int else "string"}
                if p.default is not inspect.Parameter.empty and p.default is not None:
                    sch["default"] = p.default
                if name == "limit":
                    sch.update(minimum=1, maximum=500)
                if name == "offset":
                    sch.update(minimum=0)
                op["parameters"].append({"name": name, "in": "query", "required": False, "schema": sch,
                                         "description": PARAM_DOC.get(name)})
        if not op["parameters"]:
            del op["parameters"]
        status = str(r.get("status_code", 200))
        rm = r.get("response_model")
        op["responses"][status] = {"description": "Successful Response" if status == "200" else "Accepted",
                                   "content": {"application/json": {"schema": schema_ref(rm)}} if rm else {}}
        for code, desc in ERRORS.get((r["method"], r["path"]), {}).items():
            op["responses"][code] = {"description": desc, "content": {"application/json": {"schema": {
                "type": "object", "properties": {"detail": {"type": "string"}}}}}}
        if "requestBody" in op or "parameters" in op:
            op["responses"].setdefault("422", {"description": "Validation Error", "content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}})
        paths.setdefault(path, {})[r["method"].lower()] = op
    schemas["HTTPValidationError"] = {"type": "object", "title": "HTTPValidationError", "properties": {
        "detail": {"type": "array", "title": "Detail", "items": {"$ref": "#/components/schemas/ValidationError"}}}}
    schemas["ValidationError"] = {"type": "object", "title": "ValidationError", "required": ["loc", "msg", "type"],
                                  "properties": {"loc": {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
                                                 "msg": {"type": "string"}, "type": {"type": "string"}}}
    kw = api_main.app.kw
    return {"openapi": "3.1.0",
            "info": {"title": kw["title"], "version": kw["version"], "description": kw["description"]},
            "servers": [{"url": "http://localhost:8000", "description": "Desarrollo local"}],
            "tags": kw["openapi_tags"], "paths": paths, "components": {"schemas": dict(sorted(schemas.items()))}}


def check_refs(doc):
    text = json.dumps(doc)
    for ref in set(re.findall(r'"\$ref": "#/components/schemas/(\w+)"', text)):
        assert ref in doc["components"]["schemas"], f"referencia rota: {ref}"


if __name__ == "__main__":
    doc = build()
    check_refs(doc)
    out = config.REPO_DIR / "docs" / "openapi.json"
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Escrito", out, "|", len(doc["paths"]), "rutas |", len(doc["components"]["schemas"]), "esquemas")
