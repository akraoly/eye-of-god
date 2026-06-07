from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.lifecycle import startup, shutdown
from api.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    yield
    await shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="L'Œil de Dieu — Compagnon numérique personnel ultra avancé",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Middlewares post-routing
try:
    from middleware.rag_hook import register_rag_hooks
    register_rag_hooks(app)
except Exception as _e:
    import logging
    logging.getLogger("main").warning("RAG hook middleware: %s", _e)

try:
    from middleware.rbac_middleware import register_rbac_middleware
    register_rbac_middleware(app)
except Exception as _e:
    import logging
    logging.getLogger("main").warning("RBAC middleware: %s", _e)


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
    }
