from core.agents.base_agent import BaseAgent
from core.tools.terminal import terminal

_KEYWORDS = ["scan", "nmap", "vulnérabilité", "port", "réseau", "ctf", "exploit", "shodan", "osint"]


class CyberAgent(BaseAgent):
    name = "cyber"
    description = "Expert cybersécurité — analyse réseau, vulnérabilités, CTF, OSINT"

    async def run(self, task: str, context: dict = None) -> dict:
        # Phase 1 : exécution de commandes whitelistées uniquement
        result = terminal.run(task)
        if result["success"]:
            return self._result(True, result["stdout"])
        # TODO Phase 2 : intégration LLM pour analyse + recommandations
        return self._result(False, "Commande non autorisée ou agent cyber en cours d'extension")

    def can_handle(self, task: str) -> bool:
        return any(kw in task.lower() for kw in _KEYWORDS)


cyber_agent = CyberAgent()
