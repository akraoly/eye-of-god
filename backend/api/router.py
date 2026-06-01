from fastapi import APIRouter
from api.routes import chat, memory, user, system, exploit, code, knowledge, life, observe

router = APIRouter()

router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(memory.router, prefix="/memory", tags=["Memory"])
router.include_router(user.router, prefix="/user", tags=["User"])
router.include_router(system.router, prefix="/system", tags=["System"])
router.include_router(exploit.router, prefix="/exploit", tags=["Exploit / OSEE"])
router.include_router(code.router, prefix="/code", tags=["Code / Dev"])
router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge Base"])
router.include_router(life.router, prefix="/life", tags=["Life / Personal"])
router.include_router(observe.router, prefix="/observe", tags=["Self Observation"])
