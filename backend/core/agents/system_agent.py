from core.agents.base_agent import BaseAgent
from core.tools.terminal import terminal

_KEYWORDS = ["terminal", "commande", "bash", "linux", "système", "processus", "cpu", "mémoire", "disque"]


class SystemAgent(BaseAgent):
    name = "system"
    description = "Agent système — monitoring Linux, exécution commandes sécurisées"

    async def run(self, task: str, context: dict = None) -> dict:
        result = terminal.run(task)
        if result["success"]:
            return self._result(True, result["stdout"], {"returncode": result["returncode"]})
        return self._result(False, result.get("error", "Erreur inconnue"))

    def can_handle(self, task: str) -> bool:
        return any(kw in task.lower() for kw in _KEYWORDS)


system_agent = SystemAgent()
