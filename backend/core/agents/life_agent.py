from core.agents.base_agent import BaseAgent

_KEYWORDS = ["rappel", "tâche", "agenda", "note", "projet", "objectif", "organisation", "todo"]


class LifeAgent(BaseAgent):
    name = "life"
    description = "Assistant personnel — tâches, rappels, organisation de vie"

    async def run(self, task: str, context: dict = None) -> dict:
        # TODO : intégration calendrier, rappels, gestion projets personnels
        return self._result(False, "Agent vie personnelle en cours de développement")

    def can_handle(self, task: str) -> bool:
        return any(kw in task.lower() for kw in _KEYWORDS)


life_agent = LifeAgent()
