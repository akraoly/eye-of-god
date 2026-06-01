from typing import Optional
from core.agents.cyber_agent     import cyber_agent
from core.agents.code_agent      import code_agent
from core.agents.life_agent      import life_agent
from core.agents.system_agent    import system_agent
from core.agents.knowledge_agent import knowledge_agent
from core.agents.soc_agent       import soc_agent

# SocAgent en premier — priorité sur les mots-clés SOC avant CyberAgent
AGENTS = [soc_agent, cyber_agent, code_agent, knowledge_agent, life_agent, system_agent]


class AgentService:
    async def dispatch(self, task: str, context: Optional[dict] = None) -> dict:
        for agent in AGENTS:
            if agent.can_handle(task):
                return await agent.run(task=task, context=context)
        return {
            "agent": "none",
            "success": False,
            "output": "Aucun agent disponible pour cette tâche. Passe par /chat pour une réponse IA.",
            "data": {},
        }

    def list_agents(self) -> list:
        return [{"name": a.name, "description": a.description} for a in AGENTS]


agent_service = AgentService()
