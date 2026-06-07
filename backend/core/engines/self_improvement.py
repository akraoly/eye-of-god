"""
SelfImprovementEngine — Module 20
Platform learns from every operation.
Tracks successes, failures, patterns, and auto-updates knowledge base.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from cryptography.fernet import Fernet

from app.config import settings
from core.llm.client import llm_client
from database.db import SessionLocal
from database.models import OperationOutcome, TechniqueLearning


# ── Encryption ────────────────────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    raw = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def _encrypt(data: dict) -> str:
    return _get_fernet().encrypt(json.dumps(data).encode()).decode()


def _decrypt(token: str) -> dict:
    try:
        return json.loads(_get_fernet().decrypt(token.encode()).decode())
    except Exception:
        return {}


# ── RSS feeds to monitor ──────────────────────────────────────────────────────

INTELLIGENCE_FEEDS: list[dict] = [
    {"name": "NCC Group Blog", "url": "https://research.nccgroup.com/feed/"},
    {"name": "OffSec Blog", "url": "https://www.offsec.com/blog/feed/"},
    {"name": "Project Zero", "url": "https://googleprojectzero.blogspot.com/feeds/posts/default"},
    {"name": "Rapid7 Blog", "url": "https://www.rapid7.com/blog/feed/"},
    {"name": "Synacktiv Blog", "url": "https://www.synacktiv.com/rss.xml"},
]

# Technique categories
TECHNIQUE_CATEGORIES: list[str] = [
    "reconnaissance", "initial_access", "execution", "persistence",
    "privilege_escalation", "defense_evasion", "credential_access",
    "discovery", "lateral_movement", "collection", "exfiltration",
    "impact", "web_exploitation", "network_attacks", "ad_attacks",
]

SECURITY_KEYWORDS: list[str] = [
    "exploit", "vulnerability", "CVE", "RCE", "LFI", "SSRF", "XXE",
    "privilege escalation", "lateral movement", "persistence",
    "bypass", "injection", "deserialization", "heap spray",
    "use-after-free", "buffer overflow", "race condition",
    "kerberos", "active directory", "LDAP", "SMB", "NTLM",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _db_session():
    return SessionLocal()


async def _fetch_url(url: str, timeout: int = 30) -> Optional[str]:
    """Async HTTP GET via curl subprocess."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-sL", "--max-time", str(timeout),
            "--user-agent", "Mozilla/5.0 (compatible; SecurityResearcher/1.0)",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 5)
        return stdout.decode(errors="replace")
    except Exception:
        return None


def _parse_rss(xml_content: str, max_items: int = 10) -> list[dict]:
    """Parse RSS/Atom feed XML, return list of entries."""
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # RSS 2.0
        for item in root.findall(".//item")[:max_items]:
            entry = {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "description": (item.findtext("description") or "").strip()[:500],
                "pub_date": (item.findtext("pubDate") or "").strip(),
            }
            if entry["title"]:
                items.append(entry)

        # Atom
        if not items:
            for entry_el in root.findall("atom:entry", ns)[:max_items]:
                link_el = entry_el.find("atom:link", ns)
                entry = {
                    "title": (entry_el.findtext("atom:title", "", ns) or "").strip(),
                    "link": link_el.get("href", "") if link_el is not None else "",
                    "description": (entry_el.findtext("atom:summary", "", ns) or "").strip()[:500],
                    "pub_date": (entry_el.findtext("atom:updated", "", ns) or "").strip(),
                }
                if entry["title"]:
                    items.append(entry)
    except Exception:
        pass
    return items


def _extract_techniques_from_text(text: str) -> list[str]:
    """Extract MITRE technique IDs from text."""
    return list(set(re.findall(r"T\d{4}(?:\.\d{3})?", text)))


def _is_security_relevant(title: str, description: str) -> bool:
    """Check if RSS item is relevant to security research."""
    combined = (title + " " + description).lower()
    return any(kw.lower() in combined for kw in SECURITY_KEYWORDS)


# ── SelfImprovementEngine ─────────────────────────────────────────────────────

class SelfImprovementEngine:
    """
    Platform learns from every operation.
    Tracks successes, failures, patterns, and auto-updates knowledge base.
    """

    # ── Operation outcome recording ───────────────────────────────────────────

    async def record_operation_outcome(
        self,
        operation_type: str,
        target: str,
        technique: str,
        success: bool,
        context: dict,
        reason: Optional[str] = None,
    ) -> str:
        """Record what worked/failed and why."""
        outcome_id = str(uuid.uuid4())

        # Extract target profile (OS, ports, services — if present in context)
        target_profile = {
            "target": target,
            "os": context.get("os", "unknown"),
            "services": context.get("services", []),
            "ports": context.get("ports", []),
            "domain": context.get("domain"),
        }

        # Derive tags
        tags: list[str] = [operation_type, technique]
        if success:
            tags.append("success")
        else:
            tags.append("failure")
        if "windows" in str(context).lower():
            tags.append("windows")
        if "linux" in str(context).lower():
            tags.append("linux")
        technique_ids = _extract_techniques_from_text(technique + " " + str(context))
        tags.extend(technique_ids)

        db = _db_session()
        try:
            outcome = OperationOutcome(
                outcome_id=outcome_id,
                operation_type=operation_type,
                target_profile=json.dumps(target_profile),
                technique=technique,
                success=success,
                context=_encrypt(context),
                reason=reason,
                tags=json.dumps(list(set(tags))),
                created_at=datetime.utcnow(),
            )
            db.add(outcome)
            db.commit()

            # Update TechniqueLearning table
            await self._update_technique_learning(db, technique, operation_type, success, context, target_profile)
            db.commit()
        finally:
            db.close()

        return outcome_id

    async def _update_technique_learning(
        self,
        db,
        technique: str,
        category: str,
        success: bool,
        context: dict,
        target_profile: dict,
    ):
        """Maintain per-technique success/failure stats."""
        tech_id = _extract_techniques_from_text(technique)
        tech_id_str = tech_id[0] if tech_id else technique[:20]

        existing = db.query(TechniqueLearning).filter_by(technique_id=tech_id_str).first()
        now = datetime.utcnow()

        if existing:
            if success:
                existing.success_count = (existing.success_count or 0) + 1
            else:
                existing.failure_count = (existing.failure_count or 0) + 1
            total = (existing.success_count or 0) + (existing.failure_count or 0)
            existing.success_rate = (existing.success_count or 0) / max(total, 1)
            existing.last_used = now
            existing.updated_at = now
            # Append context snapshot
            try:
                contexts_list = json.loads(existing.contexts or "[]")
                contexts_list.append({
                    "target_os": target_profile.get("os"),
                    "success": success,
                    "ts": now.isoformat(),
                })
                existing.contexts = json.dumps(contexts_list[-20:])  # keep last 20
            except Exception:
                pass
        else:
            tech = TechniqueLearning(
                technique_id=tech_id_str,
                technique_name=technique,
                category=category,
                success_rate=1.0 if success else 0.0,
                success_count=1 if success else 0,
                failure_count=0 if success else 1,
                last_used=now,
                contexts=json.dumps([{
                    "target_os": target_profile.get("os"),
                    "success": success,
                    "ts": now.isoformat(),
                }]),
                notes="",
                source_url=None,
                created_at=now,
                updated_at=now,
            )
            db.add(tech)

    # ── Post-mortem analysis ──────────────────────────────────────────────────

    async def generate_postmortem(self, job_id: str) -> dict:
        """
        Claude-powered post-mortem analysis after pentest completion.
        Extracts lessons learned, novel techniques, failure reasons,
        recommendations for future operations.
        """
        # Gather all outcomes for this job
        db = _db_session()
        try:
            # Try pentest jobs table
            try:
                from database.models import PentestJob, PentestStep
                job = db.query(PentestJob).filter_by(job_id=job_id).first()
                job_data = None
                steps_data: list = []
                if job:
                    job_data = {
                        "target": job.target,
                        "status": job.status,
                        "summary": json.loads(job.summary or "{}"),
                    }
                    steps = db.query(PentestStep).filter_by(job_id=job_id).all()
                    steps_data = [
                        {
                            "name": s.name,
                            "status": s.status,
                            "output_preview": (s.output or "")[:300],
                            "data": json.loads(s.data or "{}"),
                        }
                        for s in steps
                    ]
            except Exception:
                job_data = {"job_id": job_id}
                steps_data = []

            # Get recent operation outcomes
            outcomes = (
                db.query(OperationOutcome)
                .order_by(OperationOutcome.created_at.desc())
                .limit(20)
                .all()
            )
            outcomes_summary = [
                {
                    "type": o.operation_type,
                    "technique": o.technique,
                    "success": o.success,
                    "reason": o.reason,
                    "tags": json.loads(o.tags or "[]"),
                }
                for o in outcomes
            ]
        finally:
            db.close()

        # Build prompt for Claude
        context_str = json.dumps({
            "job": job_data,
            "steps": steps_data,
            "recent_outcomes": outcomes_summary,
        }, indent=2)

        system_prompt = (
            "You are an expert red team operator and security researcher analyzing a pentest operation. "
            "Provide structured analysis in JSON format only — no prose outside the JSON structure."
        )
        user_prompt = f"""Analyze this penetration test operation and generate a detailed post-mortem report.

OPERATION DATA:
{context_str}

Generate a JSON report with these exact keys:
- "executive_summary": string (2-3 sentences)
- "what_worked": list of strings (successful techniques)
- "what_failed": list of strings (failed techniques with reasons)
- "novel_techniques": list of strings (interesting/unusual approaches observed)
- "failure_reasons": list of {{technique, reason, mitigation}}
- "recommendations": list of strings (for future similar operations)
- "target_hardening": list of strings (what the target did right defensively)
- "skill_gaps_identified": list of strings
- "mitre_techniques_used": list of technique IDs
- "overall_score": integer 0-100 (operation effectiveness)
"""

        try:
            response = await llm_client.complete(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
                max_tokens=2048,
            )
            # Extract JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                report = json.loads(json_match.group())
            else:
                report = {"raw_analysis": response}
        except Exception as e:
            report = {
                "error": str(e),
                "executive_summary": "LLM analysis unavailable",
                "what_worked": [],
                "what_failed": [],
                "recommendations": [],
            }

        report["job_id"] = job_id
        report["generated_at"] = datetime.utcnow().isoformat()
        return report

    # ── Technique recommendations ─────────────────────────────────────────────

    async def get_technique_recommendations(self, target_profile: dict) -> list:
        """
        Based on historical operations, recommend:
        - Techniques that worked on similar targets
        - Techniques to avoid (previously failed)
        - New techniques to try
        """
        db = _db_session()
        try:
            all_techniques = db.query(TechniqueLearning).all()
            all_outcomes = (
                db.query(OperationOutcome)
                .order_by(OperationOutcome.created_at.desc())
                .limit(200)
                .all()
            )
        finally:
            db.close()

        target_os = target_profile.get("os", "").lower()
        target_services = [str(s).lower() for s in target_profile.get("services", [])]

        recommendations: list[dict] = []

        for tech in all_techniques:
            total = (tech.success_count or 0) + (tech.failure_count or 0)
            if total < 2:
                continue

            rate = tech.success_rate or 0.0
            reason = ""
            priority = 3  # 1=high, 2=medium, 3=low

            if rate >= 0.7:
                action = "recommend"
                reason = f"High success rate ({rate:.0%}) across {total} operations"
                priority = 1
            elif rate <= 0.3 and total >= 3:
                action = "avoid"
                reason = f"Low success rate ({rate:.0%}) — likely detected or mitigated"
                priority = 2
            else:
                action = "consider"
                reason = f"Moderate success rate ({rate:.0%})"
                priority = 3

            # OS affinity check
            if target_os:
                contexts_list = json.loads(tech.contexts or "[]")
                os_successes = [
                    c for c in contexts_list
                    if target_os in (c.get("target_os") or "").lower() and c.get("success")
                ]
                if os_successes:
                    priority = max(1, priority - 1)
                    reason += f" | Confirmed on {target_os}"

            recommendations.append({
                "technique_id": tech.technique_id,
                "technique_name": tech.technique_name,
                "category": tech.category,
                "action": action,
                "priority": priority,
                "success_rate": round(rate, 3),
                "total_attempts": total,
                "reason": reason,
                "last_used": tech.last_used.isoformat() if tech.last_used else None,
            })

        # Sort by priority then success rate
        recommendations.sort(key=lambda x: (x["priority"], -x["success_rate"]))
        return recommendations[:30]

    # ── Intelligence digest ───────────────────────────────────────────────────

    async def fetch_new_techniques(self) -> list:
        """
        Scrape security blogs for new techniques via RSS feeds.
        Parse and extract key techniques.
        """
        results: list[dict] = []

        for feed in INTELLIGENCE_FEEDS:
            content = await _fetch_url(feed["url"], timeout=20)
            if not content:
                continue

            items = _parse_rss(content, max_items=5)
            for item in items:
                if not _is_security_relevant(item["title"], item["description"]):
                    continue

                mitre_ids = _extract_techniques_from_text(
                    item["title"] + " " + item["description"]
                )

                results.append({
                    "source": feed["name"],
                    "title": item["title"],
                    "url": item["link"],
                    "summary": item["description"][:400],
                    "pub_date": item["pub_date"],
                    "mitre_techniques": mitre_ids,
                    "fetched_at": datetime.utcnow().isoformat(),
                })

        return results

    async def generate_training_scenario(self, skill_gaps: list) -> dict:
        """Generate CTF-style training scenario to fill skill gaps."""
        gaps_str = "\n".join(f"- {g}" for g in skill_gaps[:10])

        system = (
            "You are a cybersecurity trainer specializing in creating realistic penetration testing "
            "scenarios. Output JSON only."
        )
        prompt = f"""Create a CTF-style training scenario targeting these skill gaps:
{gaps_str}

Return JSON with:
- "title": scenario name
- "difficulty": easy/medium/hard/expert
- "description": 2-3 sentence scenario description
- "target_environment": {{os, services, vulnerabilities}}
- "objectives": list of learning objectives
- "hints": list of progressive hints
- "solution_path": list of steps to solve
- "tools_needed": list of tools
- "mitre_techniques": list of technique IDs to practice
- "estimated_time_hours": integer
- "flag_format": example flag string
"""
        try:
            response = await llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                system=system,
                max_tokens=1500,
            )
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                scenario = json.loads(json_match.group())
            else:
                scenario = {"raw": response}
        except Exception as e:
            scenario = {
                "error": str(e),
                "title": "Training scenario unavailable",
                "skill_gaps": skill_gaps,
            }

        scenario["generated_at"] = datetime.utcnow().isoformat()
        return scenario

    async def analyze_skill_gaps(self) -> dict:
        """Compare operations history to identify weak areas."""
        db = _db_session()
        try:
            techniques = db.query(TechniqueLearning).all()
            outcomes = db.query(OperationOutcome).all()
        finally:
            db.close()

        # Identify gaps: categories with no coverage or low success
        covered_categories = {t.category for t in techniques if t.technique_id}
        all_categories = set(TECHNIQUE_CATEGORIES)
        missing_categories = all_categories - covered_categories

        # Low performing techniques
        weak_techniques = [
            {
                "technique_id": t.technique_id,
                "technique_name": t.technique_name,
                "category": t.category,
                "success_rate": round(t.success_rate or 0.0, 3),
                "attempts": (t.success_count or 0) + (t.failure_count or 0),
            }
            for t in techniques
            if (t.success_rate or 0.0) < 0.4
            and ((t.success_count or 0) + (t.failure_count or 0)) >= 2
        ]

        # Overall stats
        total_ops = len(outcomes)
        successful_ops = sum(1 for o in outcomes if o.success)
        overall_success_rate = successful_ops / max(total_ops, 1)

        # Most used but least successful
        op_type_stats: dict = {}
        for o in outcomes:
            st = op_type_stats.setdefault(o.operation_type, {"success": 0, "total": 0})
            st["total"] += 1
            if o.success:
                st["success"] += 1

        worst_ops = sorted(
            [
                {
                    "operation_type": k,
                    "success_rate": round(v["success"] / v["total"], 3),
                    "total": v["total"],
                }
                for k, v in op_type_stats.items()
                if v["total"] >= 2
            ],
            key=lambda x: x["success_rate"],
        )[:5]

        skill_gaps = (
            list(missing_categories) +
            [t["technique_name"] for t in weak_techniques[:5]]
        )

        return {
            "total_operations": total_ops,
            "overall_success_rate": round(overall_success_rate, 3),
            "missing_categories": list(missing_categories),
            "weak_techniques": weak_techniques,
            "worst_operation_types": worst_ops,
            "skill_gaps": skill_gaps[:15],
            "coverage_percentage": round(len(covered_categories) / len(all_categories) * 100, 1),
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    async def update_knowledge_base(self, new_technique: dict) -> str:
        """Auto-ingest new technique into ChromaDB knowledge base."""
        try:
            from core.memory.vector_store import VectorStore
            from app.config import settings as cfg
            vs = VectorStore(chroma_dir=cfg.CHROMA_DIR)
        except Exception:
            vs = None

        # Build text document
        doc_text = (
            f"Technique: {new_technique.get('name', 'Unknown')}\n"
            f"Category: {new_technique.get('category', 'unknown')}\n"
            f"Description: {new_technique.get('description', '')}\n"
            f"MITRE ID: {new_technique.get('technique_id', '')}\n"
            f"Source: {new_technique.get('source_url', '')}\n"
            f"Steps: {new_technique.get('steps', '')}\n"
            f"Tools: {', '.join(new_technique.get('tools', []))}"
        )

        doc_id = None
        if vs:
            try:
                doc_id = vs.add(
                    doc_text,
                    metadata={
                        "type": "technique",
                        "category": new_technique.get("category", "unknown"),
                        "source": new_technique.get("source_url", ""),
                        "technique_id": new_technique.get("technique_id", ""),
                    },
                    doc_id=new_technique.get("technique_id"),
                )
            except Exception as e:
                doc_id = f"chromadb_error:{e}"

        # Also save to TechniqueLearning if has a technique_id
        if new_technique.get("technique_id"):
            db = _db_session()
            try:
                existing = db.query(TechniqueLearning).filter_by(
                    technique_id=new_technique["technique_id"]
                ).first()
                now = datetime.utcnow()
                if not existing:
                    tech = TechniqueLearning(
                        technique_id=new_technique["technique_id"],
                        technique_name=new_technique.get("name", ""),
                        category=new_technique.get("category", "unknown"),
                        success_rate=0.0,
                        success_count=0,
                        failure_count=0,
                        last_used=None,
                        contexts=json.dumps([]),
                        notes=new_technique.get("description", ""),
                        source_url=new_technique.get("source_url"),
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(tech)
                    db.commit()
                else:
                    existing.notes = new_technique.get("description", existing.notes)
                    existing.source_url = new_technique.get("source_url", existing.source_url)
                    existing.updated_at = now
                    db.commit()
            finally:
                db.close()

        return doc_id or str(uuid.uuid4())

    async def weekly_intelligence_digest(self) -> dict:
        """
        Weekly AI digest:
        - New CVEs relevant to known targets
        - New techniques from security blogs
        - Training recommendations
        - Operation stats summary
        """
        # Collect data
        new_techniques = await self.fetch_new_techniques()
        skill_gaps_data = await self.analyze_skill_gaps()

        # Recent operations stats (last 7 days)
        db = _db_session()
        try:
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_outcomes = (
                db.query(OperationOutcome)
                .filter(OperationOutcome.created_at >= week_ago)
                .all()
            )
        finally:
            db.close()

        weekly_ops = len(recent_outcomes)
        weekly_success = sum(1 for o in recent_outcomes if o.success)

        # CVE search for common services (via NVD API or NIST)
        cves: list = []
        try:
            nvd_url = "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=5&pubStartDate={}&cvssV3Severity=CRITICAL"
            start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00.000")
            nvd_content = await _fetch_url(nvd_url.format(start_date), timeout=15)
            if nvd_content:
                nvd_data = json.loads(nvd_content)
                for vuln in nvd_data.get("vulnerabilities", [])[:5]:
                    cve = vuln.get("cve", {})
                    cves.append({
                        "cve_id": cve.get("id"),
                        "description": (cve.get("descriptions", [{}])[0]).get("value", "")[:200],
                        "severity": "CRITICAL",
                    })
        except Exception:
            pass

        # Build digest with Claude
        digest_context = {
            "new_articles": len(new_techniques),
            "new_cves_critical": len(cves),
            "weekly_operations": weekly_ops,
            "weekly_success_rate": round(weekly_success / max(weekly_ops, 1), 3),
            "skill_gaps": skill_gaps_data.get("skill_gaps", [])[:5],
            "coverage": skill_gaps_data.get("coverage_percentage", 0),
            "top_new_techniques": [t["title"] for t in new_techniques[:5]],
            "critical_cves": cves[:3],
        }

        system = (
            "You are a cybersecurity intelligence analyst. Generate a concise weekly intelligence "
            "digest for a red team operator. Be specific and actionable. Output JSON only."
        )
        prompt = f"""Generate a weekly intelligence digest based on this data:
{json.dumps(digest_context, indent=2)}

Return JSON with:
- "week_summary": string (2-3 sentence overview)
- "key_threats": list of strings (top 3-5 threats this week)
- "recommended_techniques_to_practice": list of strings
- "cve_highlights": list of {{cve_id, reason_relevant}}
- "training_focus": string (what to focus on this week)
- "operational_insights": list of strings (observations from the operation stats)
- "action_items": list of strings (specific tasks for the week)
"""
        try:
            response = await llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                system=system,
                max_tokens=1500,
            )
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                ai_digest = json.loads(json_match.group())
            else:
                ai_digest = {"ai_summary": response[:1000]}
        except Exception as e:
            ai_digest = {"error": str(e)}

        return {
            "digest_date": datetime.utcnow().isoformat(),
            "period": "last_7_days",
            "stats": {
                "new_intelligence_articles": len(new_techniques),
                "critical_cves_published": len(cves),
                "operations_run": weekly_ops,
                "operations_success_rate": round(weekly_success / max(weekly_ops, 1), 3),
                "skill_coverage": skill_gaps_data.get("coverage_percentage", 0),
            },
            "new_techniques": new_techniques[:10],
            "critical_cves": cves,
            "skill_gaps": skill_gaps_data.get("skill_gaps", [])[:10],
            "ai_analysis": ai_digest,
        }

    async def get_learned_techniques(self, limit: int = 50) -> list:
        """Return all tracked techniques with learning stats."""
        db = _db_session()
        try:
            techs = (
                db.query(TechniqueLearning)
                .order_by(TechniqueLearning.success_rate.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "technique_id": t.technique_id,
                    "technique_name": t.technique_name,
                    "category": t.category,
                    "success_rate": round(t.success_rate or 0.0, 3),
                    "success_count": t.success_count or 0,
                    "failure_count": t.failure_count or 0,
                    "total_attempts": (t.success_count or 0) + (t.failure_count or 0),
                    "last_used": t.last_used.isoformat() if t.last_used else None,
                    "notes": t.notes,
                    "source_url": t.source_url,
                }
                for t in techs
            ]
        finally:
            db.close()
