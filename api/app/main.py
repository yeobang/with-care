from fastapi import FastAPI

from app.routers import health

app = FastAPI(
    title="with-care API",
    description="모든 도메인 규칙(불변식 I1~I8)은 이 API에만 산다. 앱은 Supabase에 직접 쓰지 않는다.",
)
app.include_router(health.router)
