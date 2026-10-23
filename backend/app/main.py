import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, catalog, customers, designs, geocode, projects, simulations
from app.config import get_settings

app = FastAPI(title="مصمم أنظمة الطاقة الشمسية", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if get_settings().jwt_secret == "change-me-in-production":
    logging.getLogger("uvicorn.error").warning("SOLAR_JWT_SECRET غير مضبوط؛ اضبطه قبل التشغيل الفعلي")

for module in (auth, customers, projects, designs, catalog, simulations, geocode):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
