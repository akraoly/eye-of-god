"""
OSINTAgent — Module 7.

Full OSINT reconnaissance: DNS, subdomains, Shodan, HIBP, Google dorks,
metadata, certificate transparency, infrastructure mapping.
Streaming via AsyncGenerator for SSE.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import logging
import aiohttp
from datetime import datetime
from typing import AsyncGenerator, Optional

from core.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SHODAN_API_KEY = os.environ.get("SHODAN_API_KEY", "")
HIBP_API_KEY = os.environ.get("HIBP_API_KEY", "")
CRT_SH_URL = "https://crt.sh/?q={domain}&output=json"
HIBP_BREACH_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/{account}"
HIBP_DOMAIN_URL = "https://haveibeenpwned.com/api/v3/breaches?domain={domain}"
SHODAN_HOST_URL = "https://api.shodan.io/shodan/host/{ip}?key={key}"
SHODAN_SEARCH_URL = "https://api.shodan.io/shodan/host/search?key={key}&query={query}"


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 30) -> tuple[str, bool]:
    """Run subprocess, return (output, success)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace"), proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"[TIMEOUT] {cmd[0]} exceeded {timeout}s", False
    except FileNotFoundError:
        return f"[NOT_FOUND] {cmd[0]}", False
    except Exception as exc:
        return str(exc), False


def _sse_event(event_type: str, step: str, data: dict, job_id: str = "") -> dict:
    return {
        "type": event_type,
        "job_id": job_id,
        "step": step,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }


# ── OSINTAgent ─────────────────────────────────────────────────────────────────

class OSINTAgent(BaseAgent):
    """
    Full OSINT reconnaissance for domain/org/IP.
    Chains: DNS → subdomains → Shodan → leaked creds → dorks → metadata.
    """

    name = "osint_agent"
    description = "Full OSINT recon: DNS, subdomains, Shodan, HIBP, dorks, metadata."

    async def run(self, task: str, context: Optional[dict] = None) -> dict:
        """BaseAgent interface — run full_recon on target."""
        results = {}
        async for event in self.full_recon(task, context or {}):
            if event.get("type") == "complete":
                results = event.get("data", {})
        return self._result(True, "OSINT recon completed", results)

    # ── Full recon pipeline ────────────────────────────────────────────────────

    async def full_recon(
        self, target: str, options: dict = None, job_id: str = ""
    ) -> AsyncGenerator[dict, None]:
        """
        SSE-streaming full OSINT chain.
        Steps: dns_enum, subdomain_discovery, whois, shodan,
               cert_transparency, google_dorks, leaked_creds, metadata
        """
        options = options or {}
        all_results: dict = {"target": target, "steps": {}}

        yield _sse_event("start", "init", {"message": f"OSINT recon started on {target}"}, job_id)

        # Step 1 — DNS enum
        yield _sse_event("step_start", "dns_enum", {}, job_id)
        dns = await self.dns_enum(target)
        all_results["steps"]["dns_enum"] = dns
        yield _sse_event("step_done", "dns_enum", dns, job_id)

        # Step 2 — Subdomain discovery
        yield _sse_event("step_start", "subdomain_discovery", {}, job_id)
        subs = await self.subdomain_discovery(target)
        all_results["steps"]["subdomain_discovery"] = subs
        yield _sse_event("step_done", "subdomain_discovery", subs, job_id)

        # Step 3 — WHOIS
        yield _sse_event("step_start", "whois", {}, job_id)
        whois = await self._whois(target)
        all_results["steps"]["whois"] = whois
        yield _sse_event("step_done", "whois", whois, job_id)

        # Step 4 — Shodan
        yield _sse_event("step_start", "shodan", {}, job_id)
        shodan = await self.shodan_lookup(target)
        all_results["steps"]["shodan"] = shodan
        yield _sse_event("step_done", "shodan", shodan, job_id)

        # Step 5 — Certificate transparency
        yield _sse_event("step_start", "cert_transparency", {}, job_id)
        certs = await self._cert_transparency(target)
        all_results["steps"]["cert_transparency"] = certs
        yield _sse_event("step_done", "cert_transparency", certs, job_id)

        # Step 6 — Google dorks
        yield _sse_event("step_start", "google_dorks", {}, job_id)
        dorks = await self.google_dorks(target)
        all_results["steps"]["google_dorks"] = {"dorks": dorks}
        yield _sse_event("step_done", "google_dorks", {"dorks": dorks}, job_id)

        # Step 7 — Breach check
        if options.get("check_breaches", True):
            yield _sse_event("step_start", "leaked_creds", {}, job_id)
            breach = await self.check_breach(target)
            all_results["steps"]["leaked_creds"] = breach
            yield _sse_event("step_done", "leaked_creds", breach, job_id)

        # Step 8 — Infrastructure map synthesis
        yield _sse_event("step_start", "infrastructure_map", {}, job_id)
        infra = await self.build_infrastructure_map(target, all_results)
        all_results["infrastructure_map"] = infra
        yield _sse_event("step_done", "infrastructure_map", infra, job_id)

        yield _sse_event("complete", "done", all_results, job_id)

    # ── DNS enumeration ────────────────────────────────────────────────────────

    async def dns_enum(self, domain: str) -> dict:
        """All DNS record types via dig/host/nslookup."""
        results: dict = {"domain": domain, "records": {}}
        record_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]

        if shutil.which("dig"):
            for rtype in record_types:
                out, ok = await _run(["dig", "+short", rtype, domain], timeout=10)
                if ok and out.strip():
                    results["records"][rtype] = [
                        line.strip() for line in out.strip().splitlines() if line.strip()
                    ]

            # PTR (reverse DNS) — only if A record found
            a_records = results["records"].get("A", [])
            if a_records:
                ptr_results = []
                for ip in a_records[:3]:
                    out, ok = await _run(["dig", "+short", "-x", ip], timeout=10)
                    if ok and out.strip():
                        ptr_results.append({"ip": ip, "ptr": out.strip()})
                results["records"]["PTR"] = ptr_results

            # Zone transfer attempt (AXFR)
            ns_list = results["records"].get("NS", [])
            zone_transfers = []
            for ns in ns_list[:2]:
                ns_clean = ns.rstrip(".")
                out, ok = await _run(["dig", "axfr", domain, f"@{ns_clean}"], timeout=15)
                if ok and "Transfer failed" not in out and len(out) > 100:
                    zone_transfers.append({"ns": ns_clean, "result": out[:2000]})
            if zone_transfers:
                results["zone_transfers"] = zone_transfers
                results["zone_transfer_possible"] = True

        elif shutil.which("host"):
            # Fallback: use 'host' command
            for rtype in ["A", "MX", "NS", "TXT"]:
                out, ok = await _run(["host", "-t", rtype, domain], timeout=10)
                if ok:
                    results["records"][rtype] = [
                        line.strip() for line in out.strip().splitlines() if line.strip()
                    ]

        elif shutil.which("nslookup"):
            out, ok = await _run(["nslookup", domain], timeout=10)
            if ok:
                results["nslookup_output"] = out[:1000]

        else:
            results["error"] = "No DNS tools available (dig, host, nslookup)"

        return results

    # ── Subdomain discovery ────────────────────────────────────────────────────

    async def subdomain_discovery(self, domain: str) -> dict:
        """Certificate Transparency + sublist3r + amass."""
        results: dict = {
            "domain": domain,
            "subdomains": [],
            "sources": [],
        }
        found: set = set()

        # 1. crt.sh API
        try:
            url = CRT_SH_URL.format(domain=f"%.{domain}")
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            ) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        for entry in data:
                            name = entry.get("name_value", "")
                            for sub in name.split("\n"):
                                sub = sub.strip().lstrip("*.")
                                if sub.endswith(f".{domain}") or sub == domain:
                                    found.add(sub)
                        results["sources"].append("crt.sh")
        except Exception as exc:
            logger.debug("crt.sh error: %s", exc)

        # 2. sublist3r
        if shutil.which("sublist3r"):
            out, ok = await _run(
                ["sublist3r", "-d", domain, "-o", "/dev/stdout", "--no-color"],
                timeout=60,
            )
            if ok:
                for line in out.splitlines():
                    line = line.strip()
                    if line.endswith(f".{domain}"):
                        found.add(line)
                results["sources"].append("sublist3r")

        # 3. amass (passive only to avoid noise)
        if shutil.which("amass"):
            out, ok = await _run(
                ["amass", "enum", "-passive", "-d", domain, "-timeout", "60"],
                timeout=90,
            )
            if ok:
                for line in out.splitlines():
                    line = line.strip()
                    if line.endswith(f".{domain}"):
                        found.add(line)
                results["sources"].append("amass")

        results["subdomains"] = sorted(found)
        results["count"] = len(found)
        return results

    # ── WHOIS ──────────────────────────────────────────────────────────────────

    async def _whois(self, target: str) -> dict:
        """Run whois on domain/IP."""
        if not shutil.which("whois"):
            return {"available": False, "error": "whois not installed"}
        out, ok = await _run(["whois", target], timeout=20)
        if not ok:
            return {"available": True, "success": False, "output": out[:500]}
        # Parse key fields
        parsed = {}
        for line in out.splitlines():
            for field in ["Registrar:", "Registrant:", "Creation Date:", "Updated Date:",
                          "Expiry Date:", "Name Server:", "DNSSEC:", "OrgName:", "NetRange:"]:
                if line.strip().startswith(field):
                    key = field.rstrip(":").lower().replace(" ", "_")
                    parsed.setdefault(key, []).append(line.split(":", 1)[1].strip())
        return {
            "available": True,
            "success": True,
            "target": target,
            "parsed": parsed,
            "raw": out[:3000],
        }

    # ── Certificate transparency ───────────────────────────────────────────────

    async def _cert_transparency(self, domain: str) -> dict:
        """Query crt.sh for SSL certificate history."""
        try:
            url = f"https://crt.sh/?q={domain}&output=json"
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            ) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        certs = []
                        seen_ids = set()
                        for entry in data[:50]:
                            cid = entry.get("id")
                            if cid in seen_ids:
                                continue
                            seen_ids.add(cid)
                            certs.append({
                                "id": cid,
                                "issuer": entry.get("issuer_name", ""),
                                "name": entry.get("name_value", ""),
                                "not_before": entry.get("not_before", ""),
                                "not_after": entry.get("not_after", ""),
                            })
                        return {
                            "available": True,
                            "domain": domain,
                            "cert_count": len(certs),
                            "certificates": certs[:20],
                        }
        except Exception as exc:
            logger.debug("cert_transparency error: %s", exc)
        return {"available": False, "error": "crt.sh unreachable"}

    # ── Shodan lookup ──────────────────────────────────────────────────────────

    async def shodan_lookup(self, query: str) -> dict:
        """Shodan API lookup. Requires SHODAN_API_KEY in environment."""
        key = SHODAN_API_KEY
        if not key:
            return {
                "available": False,
                "error": "SHODAN_API_KEY not set",
                "note": "Set SHODAN_API_KEY environment variable",
            }

        try:
            # Determine if query is IP or search term
            import ipaddress
            try:
                ipaddress.ip_address(query)
                url = SHODAN_HOST_URL.format(ip=query, key=key)
            except ValueError:
                url = SHODAN_SEARCH_URL.format(key=key, query=query)

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            ) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "available": True,
                            "success": True,
                            "query": query,
                            "data": data,
                        }
                    else:
                        body = await resp.text()
                        return {
                            "available": True,
                            "success": False,
                            "error": f"HTTP {resp.status}: {body[:200]}",
                        }
        except Exception as exc:
            return {"available": True, "success": False, "error": str(exc)}

    # ── Google dorks ──────────────────────────────────────────────────────────

    async def google_dorks(self, target: str) -> list:
        """
        Generate a useful list of Google dork strings for the target.
        Does NOT execute queries — returns strings only.
        """
        dorks = [
            # Information exposure
            f'site:{target}',
            f'site:{target} filetype:pdf',
            f'site:{target} filetype:xls OR filetype:xlsx',
            f'site:{target} filetype:doc OR filetype:docx',
            f'site:{target} filetype:sql',
            f'site:{target} inurl:admin',
            f'site:{target} inurl:login',
            f'site:{target} inurl:config',
            f'site:{target} inurl:wp-admin',
            f'site:{target} inurl:phpmyadmin',
            f'site:{target} inurl:.env',
            f'site:{target} inurl:backup',
            f'site:{target} intitle:"index of"',
            f'site:{target} intitle:"index of /" "parent directory"',
            # Credentials & keys
            f'site:{target} "password" filetype:txt',
            f'site:{target} "api_key" OR "apikey" OR "api key"',
            f'site:{target} "secret" OR "token"',
            # Tech fingerprinting
            f'site:{target} "powered by"',
            f'site:{target} inurl:wp-content',
            f'site:{target} inurl:.git',
            f'site:{target} inurl:.svn',
            # Error pages
            f'site:{target} "SQL syntax" OR "mysql_fetch" OR "ORA-"',
            f'site:{target} "Warning: include" OR "Warning: require"',
            f'site:{target} "Fatal error"',
            # GitHub / Pastebin leaks
            f'site:github.com "{target}"',
            f'site:pastebin.com "{target}"',
            f'site:gitlab.com "{target}"',
            f'site:trello.com "{target}"',
            # Subdomain / certificate
            f'site:*.{target}',
        ]
        return dorks

    # ── Breach check ──────────────────────────────────────────────────────────

    async def check_breach(self, email_or_domain: str) -> dict:
        """HaveIBeenPwned API check for email or domain."""
        headers = {
            "User-Agent": "EyeOfGod-OSINT/1.0",
        }
        if HIBP_API_KEY:
            headers["hibp-api-key"] = HIBP_API_KEY

        results: dict = {"target": email_or_domain, "breaches": [], "pastes": []}

        try:
            # Determine if email or domain
            is_email = "@" in email_or_domain

            if is_email:
                url = HIBP_BREACH_URL.format(account=email_or_domain)
            else:
                url = HIBP_DOMAIN_URL.format(domain=email_or_domain)

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            ) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            results["breaches"] = [
                                {
                                    "name": b.get("Name", ""),
                                    "domain": b.get("Domain", ""),
                                    "breach_date": b.get("BreachDate", ""),
                                    "pwn_count": b.get("PwnCount", 0),
                                    "data_classes": b.get("DataClasses", []),
                                    "description": b.get("Description", "")[:200],
                                }
                                for b in data
                            ]
                            results["breach_count"] = len(results["breaches"])
                    elif resp.status == 404:
                        results["breach_count"] = 0
                        results["message"] = "No breaches found"
                    elif resp.status == 401:
                        results["error"] = "HIBP API key required — set HIBP_API_KEY"
                    elif resp.status == 429:
                        results["error"] = "HIBP rate limit hit — wait before retrying"
                    else:
                        results["error"] = f"HTTP {resp.status}"
        except Exception as exc:
            results["error"] = str(exc)

        return results

    # ── Metadata extraction ────────────────────────────────────────────────────

    async def analyze_metadata(self, file_path: str) -> dict:
        """Extract metadata from a file using exiftool."""
        if not shutil.which("exiftool"):
            return {"available": False, "error": "exiftool not installed"}

        import os
        if not os.path.exists(file_path):
            return {"available": True, "success": False, "error": "file_not_found"}

        out, ok = await _run(["exiftool", "-j", file_path], timeout=30)
        if not ok:
            return {"available": True, "success": False, "output": out[:500]}

        try:
            data = json.loads(out)
            metadata = data[0] if data else {}
            # Highlight interesting fields
            interesting = {}
            for key in [
                "Author", "Creator", "LastModifiedBy", "Company", "Software",
                "GPS*", "GPSLatitude", "GPSLongitude", "GPSAltitude",
                "CreateDate", "ModifyDate", "MIMEType", "FileSize",
                "Producer", "Title", "Subject", "Keywords",
            ]:
                if key in metadata:
                    interesting[key] = metadata[key]

            return {
                "available": True,
                "success": True,
                "file": file_path,
                "metadata": metadata,
                "interesting_fields": interesting,
                "has_gps": bool(
                    metadata.get("GPSLatitude") or metadata.get("GPSLongitude")
                ),
            }
        except json.JSONDecodeError:
            return {"available": True, "success": False, "raw": out[:2000]}

    # ── Infrastructure map ─────────────────────────────────────────────────────

    async def build_infrastructure_map(self, target: str, results: dict) -> dict:
        """Synthesize all OSINT results into an infrastructure map."""
        infra: dict = {
            "target": target,
            "summary": {},
            "ip_addresses": [],
            "subdomains": [],
            "open_ports": [],
            "technologies": [],
            "certificates": [],
            "possible_vulnerabilities": [],
            "recommendations": [],
        }

        steps = results.get("steps", {})

        # IPs from DNS
        dns = steps.get("dns_enum", {})
        a_records = dns.get("records", {}).get("A", [])
        infra["ip_addresses"] = a_records

        # Subdomains
        subs = steps.get("subdomain_discovery", {})
        infra["subdomains"] = subs.get("subdomains", [])[:50]
        infra["subdomain_count"] = subs.get("count", 0)

        # Shodan data
        shodan = steps.get("shodan", {})
        if shodan.get("success"):
            data = shodan.get("data", {})
            if "ports" in data:
                infra["open_ports"] = data["ports"]
            if "data" in data:
                for svc in data["data"][:10]:
                    product = svc.get("product", "")
                    version = svc.get("version", "")
                    if product:
                        infra["technologies"].append(
                            f"{product} {version}".strip()
                        )
                # Check for vulns
                if data.get("vulns"):
                    for cve_id, cve_info in data["vulns"].items():
                        infra["possible_vulnerabilities"].append({
                            "cve": cve_id,
                            "cvss": cve_info.get("cvss", "?"),
                            "summary": cve_info.get("summary", "")[:150],
                        })

        # Certs
        certs = steps.get("cert_transparency", {})
        infra["certificate_count"] = certs.get("cert_count", 0)
        infra["certificates"] = [
            c.get("name", "") for c in certs.get("certificates", [])
        ][:20]

        # Breach data
        breach = steps.get("leaked_creds", {})
        infra["breach_count"] = breach.get("breach_count", 0)
        if breach.get("breach_count", 0) > 0:
            infra["recommendations"].append(
                "Credential exposure detected — enforce password rotation and MFA"
            )

        # Zone transfer
        if dns.get("zone_transfer_possible"):
            infra["recommendations"].append(
                "DNS zone transfer possible — restrict AXFR to authorised IPs only"
            )
            infra["possible_vulnerabilities"].append({
                "cve": "DNS Misconfiguration",
                "cvss": "MEDIUM",
                "summary": "Zone transfer (AXFR) allowed from untrusted sources",
            })

        # Summary
        infra["summary"] = {
            "ip_count": len(infra["ip_addresses"]),
            "subdomain_count": infra.get("subdomain_count", 0),
            "open_port_count": len(infra["open_ports"]),
            "tech_count": len(set(infra["technologies"])),
            "cert_count": infra["certificate_count"],
            "breach_count": infra["breach_count"],
            "vuln_count": len(infra["possible_vulnerabilities"]),
            "recommendation_count": len(infra["recommendations"]),
        }

        return infra
