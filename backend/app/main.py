from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import health, auth, teams, work_items
from app.db.session import SessionLocal
from app.services.auth_service import auth_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize / seed demo data safely on startup
    try:
        db = SessionLocal()
        try:
            auth_service.seed_demo_data(db)
        finally:
            db.close()
    except Exception as e:
        # If DB is not yet migrated, seeding will happen after migration
        pass
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(teams.router, prefix=settings.API_V1_STR)
app.include_router(work_items.router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "Welcome to Newtonite Operations Under Pressure API",
        "docs_url": "/docs",
        "health_url": "/health",
    }
