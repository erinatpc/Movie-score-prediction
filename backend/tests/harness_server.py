"""Servidor HTTP de PRUEBA para verificar la web sin FastAPI.

Monta las mismas rutas de app/main.py (los mismos manejadores, esquemas y validación de respuesta) sobre Flask.
No forma parte del producto: es solo una herramienta de verificación para entornos donde no se puede instalar FastAPI.
Uso:  python tests/harness_server.py [puerto]
"""
import asyncio
import inspect
import shutil
import sys
import tempfile
import threading
import typing
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(Path(__file__).parent)]

import _fastapi_stub  # noqa: E402

_fastapi_stub.install()
import fastapi  # noqa: E402
from flask import Flask, jsonify, request  # noqa: E402
from pydantic import BaseModel, TypeAdapter, ValidationError  # noqa: E402

from app import bootstrap, config, predictor, service  # noqa: E402
from app import main as api_main  # noqa: E402


def setup_isolated_env():
    tmp = Path(tempfile.mkdtemp(prefix="movies_harness_"))
    shutil.copytree(config.BASE_DIR / "models", tmp / "models")
    config.DB_PATH, config.MODELS_DIR = tmp / "app.db", tmp / "models"
    predictor._cache.update(version=None, pipeline=None)
    bootstrap.bootstrap()
    return tmp


def _convert(raw, ann, default):
    if raw is None:
        return default
    if typing.get_origin(ann) is typing.Union:
        ann = next(a for a in typing.get_args(ann) if a is not type(None))
    return int(raw) if ann is int else raw


def build_app():
    flask_app = Flask(__name__)

    @flask_app.after_request
    def cors(resp):
        origin = request.headers.get("Origin")
        if origin in config.CORS_ORIGINS:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Headers"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "*"
        return resp

    def make_view(route):
        handler, sig = route["handler"], inspect.signature(route["handler"])
        rm, status = route.get("response_model"), route.get("status_code", 200)

        def view(**path_args):
            kwargs, tasks = {}, None
            try:
                for name, p in sig.parameters.items():
                    ann = p.annotation
                    if ann is fastapi.BackgroundTasks:
                        tasks = kwargs[name] = fastapi.BackgroundTasks()
                    elif ann is fastapi.UploadFile:
                        f = request.files["file"]
                        kwargs[name] = fastapi.UploadFile(f.filename, f.read())
                    elif inspect.isclass(ann) and issubclass(ann, BaseModel):
                        kwargs[name] = ann.model_validate(request.get_json(force=True))
                    elif name in path_args:
                        kwargs[name] = path_args[name]
                    else:
                        kwargs[name] = _convert(request.args.get(name), ann, p.default)
                result = handler(**kwargs)
                if asyncio.iscoroutine(result):
                    result = asyncio.run(result)
                if rm is not None:                                  # misma validación que response_model
                    ta = TypeAdapter(rm)
                    result = ta.dump_python(ta.validate_python(result), mode="json")
            except service.ServiceError as e:
                return jsonify(detail=e.message), e.status
            except ValidationError as e:
                return jsonify(detail=[{"loc": ["body", *map(str, x["loc"])], "msg": x["msg"]} for x in e.errors()]), 422
            if tasks:
                for fn, a, k in tasks.tasks:
                    threading.Thread(target=fn, args=a, kwargs=k, daemon=True).start()
            return jsonify(result), status
        return view

    for i, route in enumerate(api_main.app.routes):
        rule = route["path"].replace("{run_id}", "<int:run_id>")
        flask_app.add_url_rule(rule, endpoint=f"r{i}", view_func=make_view(route),
                               methods=[route["method"]])
    return flask_app


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print("BD temporal en", setup_isolated_env(), flush=True)
    build_app().run(host="127.0.0.1", port=port, threaded=True)
