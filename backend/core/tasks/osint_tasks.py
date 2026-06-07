"""
Celery tasks — OSINT operations (long-running).
"""
import asyncio
import json

from core.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="osint_tasks.full_recon")
def full_recon_task(self, job_id: str, target: str, options: dict = None):
    """Run a full OSINT recon as a Celery background task."""
    self.update_state(state="PROGRESS", meta={"job_id": job_id, "step": "starting"})
    options = options or {}

    async def _run():
        from core.agents.osint_agent import OSINTAgent
        agent = OSINTAgent()
        results = {}
        async for event in agent.full_recon(target, options):
            # accumulate results
            if event.get("type") == "complete":
                results = event.get("data", {})
        return results

    try:
        result = asyncio.run(_run())
        return {"job_id": job_id, "status": "completed", "results": result}
    except Exception as exc:
        self.update_state(state="FAILURE", meta={"job_id": job_id, "error": str(exc)})
        raise


@celery_app.task(bind=True, name="osint_tasks.dns_enum")
def dns_enum_task(self, domain: str):
    """DNS enumeration task."""
    async def _run():
        from core.agents.osint_agent import OSINTAgent
        agent = OSINTAgent()
        return await agent.dns_enum(domain)

    return asyncio.run(_run())
