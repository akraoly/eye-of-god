from abc import ABC, abstractmethod
from typing import Optional


class BaseAgent(ABC):
    name: str = "base"
    description: str = ""

    @abstractmethod
    async def run(self, task: str, context: Optional[dict] = None) -> dict:
        pass

    def can_handle(self, task: str) -> bool:
        return False

    def _result(self, success: bool, output: str, data: Optional[dict] = None) -> dict:
        return {"agent": self.name, "success": success, "output": output, "data": data or {}}
