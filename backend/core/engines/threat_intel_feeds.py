"""
ThreatIntelFeedsEngine — Real-time threat intelligence aggregator.
Sources: NVD, CISA KEV, Exploit-DB, VirusTotal, AbuseIPDB, AlienVault OTX.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Optional

import aiohttp


class ThreatIntelFeedsEngine:
    """Real-time threat intelligence aggregator."""

    NVD_API       = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    CISA_KEV      = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    EXPLOITDB_API = "https://www.exploit-db.com/search"
    VT_API        = "https://www.virustotal.com/api/v3"
    ABUSEIPDB_API = "https://api.abuseipdb.com/api/v2/check"
    OTX_API       = "https://otx.alienvault.com/api/v1/pulses/subscribed"

    _TIMEOUT = aiohttp.ClientTimeout(total=30)

    # ── NVD ───────────────────────────────────────────────────────────────────

    async def fetch_nvd_recent(self, days: int = 7, severity: Optional[str] = None) -> list:
        """Recent CVEs from NVD with optional severity filter (CRITICAL/HIGH)."""
        now       = datetime.utcnow()
        pub_start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000")
        pub_end   = now.strftime("%Y-%m-%dT%H:%M:%S.000")

        params: dict = {
            "pubStartDate": pub_start,
            "pubEndDate": pub_end,
            "resultsPerPage": 100,
        }
        if severity:
            params["cvssV3Severity"] = severity.upper()

        try:
            async with aiohttp.ClientSession(timeout=self._TIMEOUT) as session:
                async with session.get(self.NVD_API, params=params) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
        except Exception:
            return []

        results = []
        for vuln in data.get("vulnerabilities", []):
            cve = vuln.get("cve", {})
            metrics = cve.get("metrics", {})
            cvss_score = 0.0
            cvss_vector = ""
            sev = ""

            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                mlist = metrics.get(key, [])
                if mlist:
                    m = mlist[0]
                    cvss_data = m.get("cvssData", {})
                    cvss_score  = float(cvss_data.get("baseScore", 0))
                    cvss_vector = cvss_data.get("vectorString", "")
                    sev = cvss_data.get("baseSeverity", m.get("baseSeverity", ""))
                    break

            descs = cve.get("descriptions", [])
            description = next((d["value"] for d in descs if d.get("lang") == "en"), "")

            results.append({
                "cve_id":       cve.get("id", ""),
                "identifier":   cve.get("id", ""),
                "source":       "nvd",
                "entry_type":   "cve",
                "title":        cve.get("id", ""),
                "description":  description[:500],
                "severity":     sev.upper() if sev else "UNKNOWN",
                "cvss_score":   cvss_score,
                "cvss_vector":  cvss_vector,
                "published_at": cve.get("published", ""),
                "raw_data":     vuln,
            })

        return results

    # ── CISA KEV ──────────────────────────────────────────────────────────────

    async def fetch_cisa_kev(self) -> list:
        """CISA Known Exploited Vulnerabilities catalog."""
        try:
            async with aiohttp.ClientSession(timeout=self._TIMEOUT) as session:
                async with session.get(self.CISA_KEV) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json(content_type=None)
        except Exception:
            return []

        results = []
        for vuln in data.get("vulnerabilities", []):
            results.append({
                "cve_id":             vuln.get("cveID", ""),
                "identifier":         vuln.get("cveID", ""),
                "source":             "cisa",
                "entry_type":         "cve",
                "title":              vuln.get("vulnerabilityName", ""),
                "description":        vuln.get("shortDescription", ""),
                "severity":           "CRITICAL",
                "cvss_score":         0.0,
                "affected_product":   vuln.get("product", ""),
                "vendor":             vuln.get("vendorProject", ""),
                "due_date":           vuln.get("dueDate", ""),
                "required_action":    vuln.get("requiredAction", ""),
                "published_at":       vuln.get("dateAdded", ""),
                "raw_data":           vuln,
            })

        return results

    # ── Exploit-DB ────────────────────────────────────────────────────────────

    async def fetch_exploitdb_recent(self, days: int = 7) -> list:
        """Recent public exploits from Exploit-DB (via JSON endpoint)."""
        # Exploit-DB has a GitLab mirror; fallback to search with date filter
        url = "https://www.exploit-db.com/search?date_to=" + datetime.utcnow().strftime("%Y-%m-%d")
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        params  = {
            "draw": 1,
            "start": 0,
            "length": 50,
            "search[value]": "",
        }

        try:
            async with aiohttp.ClientSession(timeout=self._TIMEOUT) as session:
                async with session.get(
                    "https://www.exploit-db.com/search",
                    params=params,
                    headers={**headers, "X-Requested-With": "XMLHttpRequest"},
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json(content_type=None)
        except Exception:
            return []

        results = []
        for item in data.get("data", []):
            results.append({
                "identifier":   str(item.get("id", "")),
                "source":       "exploitdb",
                "entry_type":   "exploit",
                "title":        item.get("description", "")[:200],
                "description":  item.get("description", ""),
                "severity":     "HIGH",
                "cvss_score":   0.0,
                "platform":     item.get("platform", {}).get("val", "") if isinstance(item.get("platform"), dict) else str(item.get("platform", "")),
                "published_at": item.get("date_published", ""),
                "raw_data":     item,
            })

        return results

    # ── VirusTotal ────────────────────────────────────────────────────────────

    async def check_virustotal(self, ioc: str, ioc_type: str, api_key: Optional[str] = None) -> dict:
        """VirusTotal lookup: file hash, URL, IP, domain."""
        if not api_key:
            return {"error": "VirusTotal API key not configured", "ioc": ioc, "ioc_type": ioc_type}

        ioc_type = ioc_type.lower()
        if ioc_type in ("md5", "sha1", "sha256", "hash"):
            url = f"{self.VT_API}/files/{ioc}"
        elif ioc_type == "url":
            import base64
            url_id = base64.urlsafe_b64encode(ioc.encode()).decode().rstrip("=")
            url = f"{self.VT_API}/urls/{url_id}"
        elif ioc_type in ("ip", "ip_address"):
            url = f"{self.VT_API}/ip_addresses/{ioc}"
        elif ioc_type in ("domain", "hostname"):
            url = f"{self.VT_API}/domains/{ioc}"
        else:
            return {"error": f"Unsupported IOC type: {ioc_type}"}

        headers = {"x-apikey": api_key}
        try:
            async with aiohttp.ClientSession(timeout=self._TIMEOUT) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 404:
                        return {"found": False, "ioc": ioc, "source": "virustotal"}
                    data = await resp.json()
        except Exception as e:
            return {"error": str(e), "ioc": ioc}

        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})
        return {
            "found":       True,
            "ioc":         ioc,
            "ioc_type":    ioc_type,
            "source":      "virustotal",
            "malicious":   stats.get("malicious", 0),
            "suspicious":  stats.get("suspicious", 0),
            "harmless":    stats.get("harmless", 0),
            "undetected":  stats.get("undetected", 0),
            "verdict":     "MALICIOUS" if stats.get("malicious", 0) > 3 else "SUSPICIOUS" if stats.get("suspicious", 0) > 1 else "CLEAN",
            "reputation":  attrs.get("reputation", 0),
            "tags":        attrs.get("tags", []),
            "raw":         attrs,
        }

    # ── AbuseIPDB ─────────────────────────────────────────────────────────────

    async def check_abuseipdb(self, ip: str, api_key: Optional[str] = None) -> dict:
        """AbuseIPDB reputation check."""
        if not api_key:
            return {"error": "AbuseIPDB API key not configured", "ip": ip}

        headers = {"Key": api_key, "Accept": "application/json"}
        params  = {"ipAddress": ip, "maxAgeInDays": 90, "verbose": True}

        try:
            async with aiohttp.ClientSession(timeout=self._TIMEOUT) as session:
                async with session.get(self.ABUSEIPDB_API, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        return {"error": f"HTTP {resp.status}", "ip": ip}
                    data = await resp.json()
        except Exception as e:
            return {"error": str(e), "ip": ip}

        d = data.get("data", {})
        return {
            "ip":             ip,
            "source":         "abuseipdb",
            "is_public":      d.get("isPublic", True),
            "abuse_score":    d.get("abuseConfidenceScore", 0),
            "country":        d.get("countryCode", ""),
            "isp":            d.get("isp", ""),
            "domain":         d.get("domain", ""),
            "total_reports":  d.get("totalReports", 0),
            "last_reported":  d.get("lastReportedAt", ""),
            "verdict":        "MALICIOUS" if d.get("abuseConfidenceScore", 0) >= 75 else "SUSPICIOUS" if d.get("abuseConfidenceScore", 0) >= 25 else "CLEAN",
            "raw":            d,
        }

    # ── AlienVault OTX ────────────────────────────────────────────────────────

    async def fetch_otx_pulse(self, api_key: Optional[str] = None) -> list:
        """AlienVault OTX threat pulses."""
        if not api_key:
            return []

        headers = {"X-OTX-API-KEY": api_key}
        params  = {"limit": 20, "modified_since": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")}

        try:
            async with aiohttp.ClientSession(timeout=self._TIMEOUT) as session:
                async with session.get(self.OTX_API, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
        except Exception:
            return []

        results = []
        for pulse in data.get("results", []):
            results.append({
                "identifier":   pulse.get("id", ""),
                "source":       "otx",
                "entry_type":   "ioc",
                "title":        pulse.get("name", ""),
                "description":  pulse.get("description", ""),
                "severity":     "MEDIUM",
                "cvss_score":   0.0,
                "tags":         pulse.get("tags", []),
                "ioc_count":    len(pulse.get("indicators", [])),
                "tlp":          pulse.get("tlp", "white"),
                "published_at": pulse.get("created", ""),
                "raw_data":     {k: v for k, v in pulse.items() if k != "indicators"},
            })

        return results

    # ── Correlation ───────────────────────────────────────────────────────────

    async def correlate_with_targets(self, cves: list, known_technologies: list) -> list:
        """Check if new CVEs affect known target technologies."""
        tech_lower = [t.lower() for t in known_technologies]
        matched = []

        for cve in cves:
            description = (cve.get("description", "") + " " + cve.get("title", "")).lower()
            affected    = cve.get("affected_product", "").lower()
            combined    = description + " " + affected

            hits = [tech for tech in tech_lower if tech and tech in combined]
            if hits:
                matched_cve = dict(cve)
                matched_cve["affects_known_target"] = True
                matched_cve["matched_technologies"]  = hits
                matched.append(matched_cve)

        return matched

    # ── Aggregate all ─────────────────────────────────────────────────────────

    async def aggregate_all(self) -> dict:
        """Fetch all feeds concurrently, return unified threat picture."""
        tasks = [
            self.fetch_nvd_recent(days=7),
            self.fetch_cisa_kev(),
            self.fetch_exploitdb_recent(days=7),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        nvd_results   = results[0] if not isinstance(results[0], Exception) else []
        cisa_results  = results[1] if not isinstance(results[1], Exception) else []
        edb_results   = results[2] if not isinstance(results[2], Exception) else []

        all_entries = nvd_results + cisa_results + edb_results

        critical_cves = [
            e for e in nvd_results + cisa_results
            if e.get("severity") in ("CRITICAL", "HIGH") or float(e.get("cvss_score", 0)) >= 7.0
        ]

        return {
            "fetched_at":      datetime.utcnow().isoformat(),
            "total_entries":   len(all_entries),
            "nvd_count":       len(nvd_results),
            "cisa_count":      len(cisa_results),
            "exploitdb_count": len(edb_results),
            "critical_count":  len([e for e in all_entries if e.get("severity") == "CRITICAL"]),
            "high_count":      len([e for e in all_entries if e.get("severity") == "HIGH"]),
            "critical_cves":   critical_cves,
            "all_entries":     all_entries,
        }

    # ── IOC Search ────────────────────────────────────────────────────────────

    async def search_ioc(self, ioc: str) -> dict:
        """Search IOC across all available sources (without API keys)."""
        result: dict = {
            "ioc":     ioc,
            "sources": {},
        }

        # Detect IOC type
        ip_pattern  = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
        hash_pattern = re.compile(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$")

        if ip_pattern.match(ioc):
            result["ioc_type"] = "ip"
        elif hash_pattern.match(ioc):
            result["ioc_type"] = "hash"
            result["hash_type"] = "md5" if len(ioc) == 32 else "sha1" if len(ioc) == 40 else "sha256"
        elif "@" in ioc:
            result["ioc_type"] = "email"
        elif "http" in ioc:
            result["ioc_type"] = "url"
        else:
            result["ioc_type"] = "domain"

        result["sources"]["note"] = "API keys required for VirusTotal, AbuseIPDB, OTX lookups"
        return result
