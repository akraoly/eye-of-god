from fastapi import APIRouter
from api.routes import chat, memory, user, system, exploit, code

router = APIRouter()

router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(memory.router, prefix="/memory", tags=["Memory"])
router.include_router(user.router, prefix="/user", tags=["User"])
router.include_router(system.router, prefix="/system", tags=["System"])
router.include_router(exploit.router, prefix="/exploit", tags=["Exploit / OSEE"])
router.include_router(code.router, prefix="/code", tags=["Code / Dev"])
