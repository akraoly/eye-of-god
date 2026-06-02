from fastapi import APIRouter
from api.routes import chat, memory, user, system, exploit, code, knowledge, life, observe, soc, offensive, c2

router = APIRouter()

router.include_router(chat.router,      prefix="/chat",      tags=["Chat"])
router.include_router(memory.router,    prefix="/memory",    tags=["Memory"])
router.include_router(user.router,      prefix="/user",      tags=["User"])
router.include_router(system.router,    prefix="/system",    tags=["System"])
router.include_router(exploit.router,   prefix="/exploit",   tags=["Exploit / OSEE"])
router.include_router(code.router,      prefix="/code",      tags=["Code / Dev"])
router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge Base"])
router.include_router(life.router,      prefix="/life",      tags=["Life / Personal"])
router.include_router(observe.router,   prefix="/observe",   tags=["Self Observation"])
router.include_router(soc.router,       prefix="/soc",       tags=["SOC"])
router.include_router(offensive.router, prefix="/offensive", tags=["Offensive — 4 Niveaux"])
router.include_router(c2.router,        prefix="/c2",        tags=["C2 — Frameworks"])
