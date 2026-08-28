from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.domain.errors import InvariantViolation
from app.routers import board, crews, health, photos, users

app = FastAPI(
    title="with-care API",
    description="모든 도메인 규칙(불변식 I1~I8)은 이 API에만 산다. 앱은 Supabase에 직접 쓰지 않는다.",
)
# dev: Expo 웹(8081)에서의 호출 허용. prod 오리진은 배포 시 확정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(users.router)
app.include_router(crews.router)
app.include_router(board.router)
app.include_router(photos.router)


@app.exception_handler(InvariantViolation)
def invariant_handler(request: Request, exc: InvariantViolation) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"invariant": exc.invariant, "detail": str(exc)},
    )


@app.exception_handler(ValueError)
def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})
