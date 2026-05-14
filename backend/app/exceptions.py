# exceptions.py（示例）
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code


def _http_detail_to_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                loc = item.get("loc", ())
                msg = item.get("msg", "")
                parts.append(f"{'/'.join(str(x) for x in loc)}: {msg}")
            else:
                parts.append(str(item))
        return "; ".join(parts) if parts else "请求参数无效"
    if isinstance(detail, dict):
        return str(detail.get("msg") or detail)
    return "请求失败"

    
def api_error_dict(*, code: int, message: str) -> dict:
    """与 ApiResponse 字段一致，供异常处理器 JSON 返回（非 0 的 code 表示失败）。"""
    return {"code": code, "message": message, "data": None}


def register_exception_handler(app: FastAPI):
    """注册异常处理器"""
    
    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(status_code=exc.code, content=api_error_dict(code=exc.code, message=exc.message))

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        msg = _http_detail_to_message(exc.detail)
        code = exc.status_code if exc.status_code >= 400 else 500
        return JSONResponse(status_code=exc.status_code, content=api_error_dict(code=code, message=msg))


    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        msg = _http_detail_to_message(exc.errors())
        return JSONResponse(
            status_code=422,
            content=api_error_dict(code=422, message=msg or "请求参数无效"),
        )    