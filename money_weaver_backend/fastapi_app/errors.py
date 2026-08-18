from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_error_handlers(app: FastAPI):
    @app.exception_handler(HTTPException)
    async def http_exc(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={'error': exc.detail})

    @app.exception_handler(RequestValidationError)
    async def val_exc(request: Request, exc: RequestValidationError):
        first = exc.errors()[0]
        msg = first['msg'] if first['loc'] == ('body',) else f"{first['loc'][-1]}: {first['msg']}"
        return JSONResponse(status_code=400, content={'error': msg})