"""Sustituto MÍNIMO de FastAPI, solo para poder probar los manejadores cuando FastAPI no está instalado
(p. ej. en entornos sin red). Si FastAPI está instalado, esto no se usa."""
import sys
import types


def install():
    try:
        import fastapi  # noqa: F401
        return False
    except ImportError:
        pass

    class FastAPI:
        def __init__(self, **kw):
            self.kw, self.routes = kw, []

        def add_middleware(self, *a, **k):
            pass

        def exception_handler(self, exc):
            return lambda f: f

        def _reg(self, method, path, **kw):
            def deco(f):
                self.routes.append({"method": method, "path": path, "handler": f, **kw})
                return f
            return deco

        def get(self, path, **kw):
            return self._reg("GET", path, **kw)

        def post(self, path, **kw):
            return self._reg("POST", path, **kw)

    class BackgroundTasks:
        def __init__(self):
            self.tasks = []

        def add_task(self, fn, *a, **k):
            self.tasks.append((fn, a, k))

    class UploadFile:
        def __init__(self, filename, data):
            self.filename, self._data = filename, data

        async def read(self):
            return self._data

    class JSONResponse:
        def __init__(self, status_code=200, content=None):
            self.status_code, self.content = status_code, content

    fa = types.ModuleType("fastapi")
    fa.FastAPI, fa.BackgroundTasks, fa.UploadFile = FastAPI, BackgroundTasks, UploadFile
    fa.File = lambda *a, **k: None
    fa.Query = lambda default=None, **k: default
    mw = types.ModuleType("fastapi.middleware")
    cors = types.ModuleType("fastapi.middleware.cors")
    cors.CORSMiddleware = object
    rs = types.ModuleType("fastapi.responses")
    rs.JSONResponse = JSONResponse
    sys.modules.update({"fastapi": fa, "fastapi.middleware": mw, "fastapi.middleware.cors": cors,
                        "fastapi.responses": rs})
    return True
