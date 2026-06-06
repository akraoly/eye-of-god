from fastapi import APIRouter, Depends
from api.routes import chat, memory, user, system, exploit, code, knowledge, life, observe, soc, offensive, c2, auth, vision, autonomy
from api.routes import c2_unified
from core.auth.dependencies import get_current_user

router = APIRouter()

# Route publique — pas de token requis
router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# Routes protégées
_protected = {"dependencies": [Depends(get_current_user)]}

router.include_router(chat.router,      prefix="/chat",      tags=["Chat"],                       **_protected)
router.include_router(memory.router,    prefix="/memory",    tags=["Memory"],                     **_protected)
router.include_router(user.router,      prefix="/user",      tags=["User"],                       **_protected)
router.include_router(system.router,    prefix="/system",    tags=["System"],                     **_protected)
router.include_router(exploit.router,   prefix="/exploit",   tags=["Exploit / OSEE"],             **_protected)
router.include_router(code.router,      prefix="/code",      tags=["Code / Dev"],                 **_protected)
router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge Base"],             **_protected)
router.include_router(life.router,      prefix="/life",      tags=["Life / Personal"],            **_protected)
router.include_router(observe.router,   prefix="/observe",   tags=["Self Observation"],           **_protected)
router.include_router(soc.router,       prefix="/soc",       tags=["SOC"],                        **_protected)
router.include_router(offensive.router, prefix="/offensive", tags=["Offensive — 4 Niveaux"],     **_protected)
router.include_router(c2.router,        prefix="/c2",        tags=["C2 — Frameworks"],            **_protected)
router.include_router(c2_unified.router, prefix="/c2/unified", tags=["C2 Manager Unifié"],         **_protected)
router.include_router(vision.router,    prefix="/vision",    tags=["Vision"],                     **_protected)
router.include_router(autonomy.router,  prefix="/autonomy",  tags=["Autonomy"],                   **_protected)
