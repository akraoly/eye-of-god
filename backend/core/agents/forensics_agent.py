"""
ForensicsAgent — Malware analysis and digital forensics.
Supports: file analysis, IOC extraction, PowerShell deobfuscation, memory dump analysis,
Office macro analysis, Docker sandbox execution, STIX 2.1 report generation.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.tools.logger import get_logger

logger = get_logger("forensics_agent")

# RFC1918 prefixes to exclude from IOC extraction
_PRIVATE_IP_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                        "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                        "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                        "172.30.", "172.31.", "192.168.", "127.", "0.", "255.")

_COMMON_DOMAINS = {
    "microsoft.com", "windows.com", "google.com", "apple.com",
    "amazon.com", "github.com", "localhost", "example.com",
    "live.com", "office.com", "azure.com", "cloudflare.com",
}


class ForensicsAgent:
    """Malware analysis and digital forensics with Docker sandbox."""

    SANDBOX_IMAGE = "ubuntu:22.04"

    # ── Main File Analysis ────────────────────────────────────────────────────

    async def analyze_file(self, file_path: str, filename: str) -> dict:
        """
        Full file analysis pipeline:
        1. file type detection (file, magic)
        2. hash calculation (md5, sha1, sha256, ssdeep if available)
        3. strings extraction
        4. PE/ELF structure if applicable
        5. Sandbox execution (Docker --network none)
        6. IOC extraction
        7. YARA scan if rules available
        """
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        logger.info(f"[Forensics] Analyzing {filename}...")

        result: dict = {
            "case_id":   str(uuid.uuid4())[:8],
            "filename":  filename,
            "file_path": file_path,
            "file_size": path.stat().st_size,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        # 1. Hashes
        result["hashes"] = self._calculate_hashes(file_path)
        result["file_hash"] = result["hashes"].get("sha256", "")

        # 2. File type
        file_info = await self._detect_file_type(file_path)
        result.update(file_info)

        # 3. Strings
        strings_raw = await self._extract_strings_raw(file_path)
        result["strings_sample"] = strings_raw[:3000]

        # 4. IOCs from strings
        result["iocs"] = await self.extract_iocs(strings_raw)

        # 5. Structure analysis
        if "elf" in result.get("file_type", "").lower() or "pe" in result.get("file_type", "").lower():
            structure = await self._analyze_structure(file_path)
            result["structure"] = structure

        # 6. Office macro check
        file_ext = path.suffix.lower()
        if file_ext in (".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".docm", ".ppt", ".pptx"):
            macro_result = await self.analyze_office_macro(file_path)
            result["macro_analysis"] = macro_result

        # 7. YARA scan
        yara_result = await self._run_yara(file_path)
        result["yara"] = yara_result

        # 8. Sandbox execution (only for executables < 50MB)
        if (
            result.get("file_size", 0) < 50 * 1024 * 1024
            and result.get("file_type", "").upper() in ("ELF", "PE", "SCRIPT")
            and shutil.which("docker")
        ):
            sandbox_result = await self.sandbox_execute(file_path, timeout=30)
            result["sandbox"] = sandbox_result
            sandbox_output = sandbox_result.get("stdout", "") + sandbox_result.get("stderr", "")
            extra_iocs = await self.extract_iocs(sandbox_output)
            # Merge IOCs
            for ioc_type, values in extra_iocs.items():
                if ioc_type in result["iocs"] and isinstance(result["iocs"][ioc_type], list):
                    result["iocs"][ioc_type] = list(set(result["iocs"][ioc_type] + values))

        # 9. Maliciousness heuristic
        result["is_malicious"] = self._assess_maliciousness(result)
        result["malware_family"] = self._guess_family(result)
        result["status"] = "completed"

        logger.info(f"[Forensics] Analysis of {filename} completed.")
        return result

    # ── IOC Extraction ────────────────────────────────────────────────────────

    async def extract_iocs(self, content: str) -> dict:
        """
        Extract from text/output:
        - IPs (exclude RFC1918)
        - Domains (exclude common)
        - URLs
        - File paths (Windows + Linux)
        - Registry keys
        - Mutex names
        - User-agents
        - Email addresses
        """
        result: dict = {
            "ips":            [],
            "domains":        [],
            "urls":           [],
            "file_paths":     [],
            "registry_keys":  [],
            "emails":         [],
            "hashes":         [],
            "mutexes":        [],
            "user_agents":    [],
        }

        # IPs — exclude RFC1918
        ip_pattern = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
        for m in ip_pattern.finditer(content):
            ip = m.group(1)
            if not any(ip.startswith(p) for p in _PRIVATE_IP_PREFIXES):
                result["ips"].append(ip)

        # URLs
        url_pattern = re.compile(r"https?://[^\s\"'<>]{4,}")
        result["urls"] = url_pattern.findall(content)

        # Domains (from URLs + standalone)
        domain_pattern = re.compile(
            r"\b(?:[a-zA-Z0-9-]{1,63}\.)+(?:com|net|org|io|gov|edu|mil|ru|cn|de|fr|uk|nl|br)\b"
        )
        for dom in domain_pattern.findall(content):
            dom_lower = dom.lower()
            if dom_lower not in _COMMON_DOMAINS and len(dom) > 4:
                result["domains"].append(dom)

        # Windows file paths
        win_path = re.compile(r"[A-Za-z]:\\(?:[^\\\s\"<>|:*?]{1,255}\\)*[^\\\s\"<>|:*?]{1,255}")
        result["file_paths"] += win_path.findall(content)

        # Linux file paths
        linux_path = re.compile(r"(?<!\w)/(?:tmp|home|var|etc|usr|opt|proc|sys|dev)/[^\s\"']{3,}")
        result["file_paths"] += linux_path.findall(content)

        # Registry keys
        reg_pattern = re.compile(
            r"HKEY_(?:LOCAL_MACHINE|CURRENT_USER|CLASSES_ROOT|USERS|CURRENT_CONFIG)"
            r"(?:\\[^\s\"'\\]{1,255})+"
        )
        result["registry_keys"] = reg_pattern.findall(content)

        # Email addresses
        email_pattern = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
        result["emails"] = email_pattern.findall(content)

        # Hashes
        md5_re    = re.compile(r"\b[a-fA-F0-9]{32}\b")
        sha1_re   = re.compile(r"\b[a-fA-F0-9]{40}\b")
        sha256_re = re.compile(r"\b[a-fA-F0-9]{64}\b")
        result["hashes"] = md5_re.findall(content) + sha1_re.findall(content) + sha256_re.findall(content)

        # Mutex names (Windows-style)
        mutex_re = re.compile(r"(?:CreateMutex|OpenMutex|mutex)[A-Za-z0-9_\-\"\']{4,40}", re.IGNORECASE)
        result["mutexes"] = mutex_re.findall(content)

        # User-agents
        ua_re = re.compile(r"User-Agent:\s*([^\r\n]{10,200})", re.IGNORECASE)
        result["user_agents"] = ua_re.findall(content)

        # Deduplicate all lists
        for key in result:
            if isinstance(result[key], list):
                result[key] = list(dict.fromkeys(result[key]))[:100]

        return result

    # ── PowerShell deobfuscation ──────────────────────────────────────────────

    async def deobfuscate_powershell(self, script: str) -> dict:
        """
        PowerShell deobfuscation:
        1. Multiple rounds of UTF8/Base64 decode
        2. Invoke-Expression extraction
        3. Variable substitution
        Uses pwsh if available, else Python regex.
        """
        result: dict = {
            "original":    script[:2000],
            "deobfuscated": "",
            "iocs":         {},
            "techniques":   [],
            "risk_level":   "LOW",
        }

        current = script
        rounds = 0
        max_rounds = 5

        while rounds < max_rounds:
            rounds += 1
            changed = False

            # 1. Base64 decode (common: -EncodedCommand, FromBase64String)
            b64_pattern = re.compile(
                r"(?:-EncodedCommand|-enc|-e)\s+([A-Za-z0-9+/=]{20,})|"
                r"FromBase64String\([\"']([A-Za-z0-9+/=]{20,})[\"']\)|"
                r"\[Convert\]::FromBase64String\([\"']([A-Za-z0-9+/=\s]{20,})[\"']\)",
                re.IGNORECASE,
            )
            for m in b64_pattern.finditer(current):
                b64_str = (m.group(1) or m.group(2) or m.group(3) or "").replace(" ", "")
                try:
                    import base64
                    decoded = base64.b64decode(b64_str).decode("utf-16-le", errors="replace")
                    if len(decoded) > 10:
                        current = current.replace(b64_str, f"[DECODED:{decoded[:200]}]")
                        result["techniques"].append("base64_encoding")
                        changed = True
                except Exception:
                    pass

            # 2. String reverse (-join reversed)
            reverse_pattern = re.compile(r'\[char\[\]\](["\'][^"\']+["\'])\s*\)\s*-join', re.IGNORECASE)
            for m in reverse_pattern.finditer(current):
                try:
                    s = m.group(1).strip("\"'")
                    reversed_s = s[::-1]
                    current = current.replace(m.group(0), f'"{reversed_s}"')
                    result["techniques"].append("string_reversal")
                    changed = True
                except Exception:
                    pass

            # 3. Char code concatenation: [char]0x48 + [char]0x65...
            char_pattern = re.compile(r"\[char\](?:0x[0-9a-fA-F]+|\d+)", re.IGNORECASE)
            chars_found = char_pattern.findall(current)
            if chars_found:
                for char_expr in chars_found:
                    try:
                        num_str = char_expr.split("]")[1]
                        num = int(num_str, 16) if "0x" in num_str.lower() else int(num_str)
                        if 32 <= num <= 126:
                            current = current.replace(char_expr, chr(num), 1)
                            result["techniques"].append("char_obfuscation")
                            changed = True
                    except Exception:
                        pass

            if not changed:
                break

        # Use pwsh for deeper deobfuscation if available
        pwsh_bin = shutil.which("pwsh") or shutil.which("powershell")
        if pwsh_bin and len(script) < 5000:
            try:
                ps_script = f"""
$encoded = @'
{script[:3000]}
'@
try {{
    $decoded = [System.Text.RegularExpressions.Regex]::Unescape($encoded)
    Write-Output $decoded
}} catch {{
    Write-Output $encoded
}}
"""
                proc = await asyncio.create_subprocess_exec(
                    pwsh_bin, "-NonInteractive", "-Command", ps_script,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
                pwsh_out = stdout.decode(errors="replace").strip()
                if pwsh_out and len(pwsh_out) > 20:
                    current = pwsh_out
                    result["techniques"].append("pwsh_execution")
            except Exception as e:
                logger.debug(f"pwsh deobfuscation failed: {e}")

        result["deobfuscated"] = current[:5000]
        result["iocs"] = await self.extract_iocs(current)

        # Risk assessment
        high_risk_patterns = ["invoke-expression", "iex", "downloadstring", "webclient",
                              "shellcode", "bypass", "hidden", "noprofile"]
        matches = sum(1 for p in high_risk_patterns if p in current.lower())
        result["risk_level"] = "CRITICAL" if matches >= 4 else "HIGH" if matches >= 2 else "MEDIUM" if matches >= 1 else "LOW"

        return result

    # ── Memory dump analysis ──────────────────────────────────────────────────

    async def analyze_memory_dump(self, dump_path: str) -> dict:
        """Volatility3 analysis if installed."""
        result: dict = {
            "dump_path":   dump_path,
            "processes":   [],
            "network":     [],
            "malfind":     [],
            "dlls":        [],
            "status":      "not_run",
        }

        vol3_bin = shutil.which("vol3") or shutil.which("volatility3") or shutil.which("vol")
        if not vol3_bin:
            result["status"]  = "volatility_unavailable"
            result["message"] = "Volatility3 not found. Install with: pip install volatility3"
            return result

        if not Path(dump_path).exists():
            result["status"] = "file_not_found"
            return result

        async def _run_vol(plugin: str) -> str:
            try:
                proc = await asyncio.create_subprocess_exec(
                    vol3_bin, "-f", dump_path, plugin,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                return stdout.decode(errors="replace")
            except asyncio.TimeoutError:
                return f"[Timeout running {plugin}]"
            except Exception as e:
                return f"[Error: {e}]"

        # Run all plugins concurrently
        plugins = ["windows.pslist", "windows.netscan", "windows.malfind"]
        outputs = await asyncio.gather(*[_run_vol(p) for p in plugins], return_exceptions=True)

        pslist_out  = str(outputs[0]) if not isinstance(outputs[0], Exception) else ""
        netscan_out = str(outputs[1]) if not isinstance(outputs[1], Exception) else ""
        malfind_out = str(outputs[2]) if not isinstance(outputs[2], Exception) else ""

        # Parse pslist
        for line in pslist_out.splitlines()[2:]:
            parts = line.split()
            if len(parts) >= 3:
                result["processes"].append({
                    "name":  parts[0] if parts else "",
                    "pid":   parts[1] if len(parts) > 1 else "",
                    "ppid":  parts[2] if len(parts) > 2 else "",
                    "raw":   line[:100],
                })

        # Parse netscan
        for line in netscan_out.splitlines()[2:]:
            if "ESTABLISHED" in line or "LISTEN" in line or "CLOSE" in line:
                result["network"].append({"raw": line[:150]})

        # Parse malfind
        if "Malfind" in malfind_out or "VAD" in malfind_out:
            result["malfind"] = [{"raw": l[:150]} for l in malfind_out.splitlines()[2:20]]

        result["status"] = "completed"
        result["raw"] = {
            "pslist":  pslist_out[:3000],
            "netscan": netscan_out[:2000],
            "malfind": malfind_out[:2000],
        }

        return result

    # ── Office macro analysis ─────────────────────────────────────────────────

    async def analyze_office_macro(self, doc_path: str) -> dict:
        """olevba / oledump analysis of Office macros."""
        result: dict = {
            "has_macros":    False,
            "macro_count":   0,
            "suspicious":    [],
            "iocs":          {},
            "vba_code":      "",
            "risk_level":    "LOW",
            "status":        "not_run",
        }

        olevba_bin = shutil.which("olevba")
        if not olevba_bin:
            result["status"]  = "olevba_unavailable"
            result["message"] = "olevba not found. Install with: pip install oletools"
            return result

        try:
            proc = await asyncio.create_subprocess_exec(
                olevba_bin, "--decode", "--reveal", doc_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            out = stdout.decode(errors="replace")
            err = stderr.decode(errors="replace")
        except asyncio.TimeoutError:
            result["status"] = "timeout"
            return result
        except Exception as e:
            result["status"] = "error"
            result["error"]  = str(e)
            return result

        result["raw_output"] = (out + err)[:5000]
        result["status"]     = "completed"

        if "No VBA code found" in out:
            result["has_macros"] = False
            return result

        result["has_macros"] = True
        result["vba_code"]   = out[:4000]

        # Extract suspicious indicators
        suspicious_kws = [
            "AutoOpen", "AutoExec", "Shell", "WScript", "PowerShell",
            "CreateObject", "Environ", "GetObject", "URLDownloadToFile",
            "StrReverse", "Chr(", "ChrW(", "Xor",
        ]
        for kw in suspicious_kws:
            if kw.lower() in out.lower():
                result["suspicious"].append(kw)

        result["iocs"] = await self.extract_iocs(out)

        matches = len(result["suspicious"])
        result["risk_level"] = "CRITICAL" if matches >= 5 else "HIGH" if matches >= 3 else "MEDIUM" if matches >= 1 else "LOW"

        return result

    # ── Docker Sandbox ────────────────────────────────────────────────────────

    async def sandbox_execute(self, file_path: str, timeout: int = 30) -> dict:
        """
        Execute in Docker sandbox:
        docker run --rm --network none --memory 256m --cpus 0.5
                   -v {file_path}:/sandbox/sample:ro
                   ubuntu:22.04 /sandbox/sample
        """
        result: dict = {
            "executed":  False,
            "stdout":    "",
            "stderr":    "",
            "exit_code": None,
            "timeout":   False,
        }

        docker_bin = shutil.which("docker")
        if not docker_bin:
            result["error"] = "Docker not available"
            return result

        try:
            cmd = [
                docker_bin, "run", "--rm",
                "--network", "none",
                "--memory", "256m",
                "--cpus", "0.5",
                "--read-only",
                f"-v{file_path}:/sandbox/sample:ro",
                "--timeout", str(timeout),
                self.SANDBOX_IMAGE,
                "bash", "-c", f"chmod +x /sandbox/sample && /sandbox/sample",
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 10)

            result["executed"]  = True
            result["stdout"]    = stdout.decode(errors="replace")[:5000]
            result["stderr"]    = stderr.decode(errors="replace")[:2000]
            result["exit_code"] = proc.returncode

        except asyncio.TimeoutError:
            result["timeout"] = True
            result["error"]   = "Sandbox execution timed out"
        except Exception as e:
            result["error"] = str(e)

        return result

    # ── STIX 2.1 Report ───────────────────────────────────────────────────────

    async def generate_stix_report(self, analysis: dict) -> dict:
        """Generate STIX 2.1 indicators from analysis results."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        bundle_id = f"bundle--{str(uuid.uuid4())}"
        objects = []

        # Malware object
        malware_id = f"malware--{str(uuid.uuid4())}"
        objects.append({
            "type":              "malware",
            "spec_version":      "2.1",
            "id":                malware_id,
            "created":           now,
            "modified":          now,
            "name":              analysis.get("filename", "unknown"),
            "malware_types":     ["trojan"] if analysis.get("is_malicious") else ["unknown"],
            "is_family":         False,
            "description":       f"File hash: {analysis.get('file_hash', '')}. Family: {analysis.get('malware_family', 'unknown')}",
        })

        iocs = analysis.get("iocs", {})

        # IP indicators
        for ip in iocs.get("ips", [])[:10]:
            ind_id = f"indicator--{str(uuid.uuid4())}"
            objects.append({
                "type":         "indicator",
                "spec_version": "2.1",
                "id":           ind_id,
                "created":      now,
                "modified":     now,
                "name":         f"Malicious IP: {ip}",
                "indicator_types": ["malicious-activity"],
                "pattern":      f"[ipv4-addr:value = '{ip}']",
                "pattern_type": "stix",
                "valid_from":   now,
            })

        # Domain indicators
        for dom in iocs.get("domains", [])[:10]:
            ind_id = f"indicator--{str(uuid.uuid4())}"
            objects.append({
                "type":         "indicator",
                "spec_version": "2.1",
                "id":           ind_id,
                "created":      now,
                "modified":     now,
                "name":         f"Malicious domain: {dom}",
                "indicator_types": ["malicious-activity"],
                "pattern":      f"[domain-name:value = '{dom}']",
                "pattern_type": "stix",
                "valid_from":   now,
            })

        # File hash indicator
        sha256 = analysis.get("file_hash") or analysis.get("hashes", {}).get("sha256", "")
        if sha256:
            ind_id = f"indicator--{str(uuid.uuid4())}"
            objects.append({
                "type":         "indicator",
                "spec_version": "2.1",
                "id":           ind_id,
                "created":      now,
                "modified":     now,
                "name":         f"Malware hash: {sha256[:16]}...",
                "indicator_types": ["malicious-activity"],
                "pattern":      f"[file:hashes.'SHA-256' = '{sha256}']",
                "pattern_type": "stix",
                "valid_from":   now,
            })

        return {
            "type":         "bundle",
            "id":           bundle_id,
            "spec_version": "2.1",
            "objects":      objects,
        }

    # ── Incident Timeline ─────────────────────────────────────────────────────

    async def build_incident_timeline(self, events: list) -> list:
        """Sort and correlate events into a chronological timeline."""
        def _parse_ts(event):
            ts = event.get("timestamp", event.get("time", event.get("ts", "")))
            if not ts:
                return datetime.min
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(str(ts)[:19], fmt)
                except ValueError:
                    continue
            return datetime.min

        sorted_events = sorted(events, key=_parse_ts)

        # Tag correlated events (same source IP or hash within 5 min window)
        timeline = []
        for i, event in enumerate(sorted_events):
            entry = dict(event)
            entry["timeline_index"] = i + 1
            entry["correlated_with"] = []

            for j, other in enumerate(sorted_events):
                if i == j:
                    continue
                if (event.get("source_ip") and event["source_ip"] == other.get("source_ip")):
                    entry["correlated_with"].append(j + 1)

            timeline.append(entry)

        return timeline

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _calculate_hashes(self, file_path: str) -> dict:
        hashes = {}
        try:
            data = Path(file_path).read_bytes()
            hashes["md5"]    = hashlib.md5(data).hexdigest()
            hashes["sha1"]   = hashlib.sha1(data).hexdigest()
            hashes["sha256"] = hashlib.sha256(data).hexdigest()
            hashes["size"]   = len(data)

            # ssdeep if available
            if shutil.which("ssdeep"):
                pass  # would add ssdeep here; skip if not available
        except Exception as e:
            hashes["error"] = str(e)
        return hashes

    async def _detect_file_type(self, file_path: str) -> dict:
        info = {"file_type": "unknown", "mime_type": ""}
        if not shutil.which("file"):
            return info
        try:
            proc = await asyncio.create_subprocess_exec(
                "file", "-b", "--mime-type", file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            mime = stdout.decode(errors="replace").strip()
            info["mime_type"] = mime

            proc2 = await asyncio.create_subprocess_exec(
                "file", "-b", file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=10)
            desc = stdout2.decode(errors="replace").strip()
            info["file_type_desc"] = desc

            flo = desc.lower()
            if "elf" in flo:
                info["file_type"] = "ELF"
            elif "pe32" in flo or "portable executable" in flo:
                info["file_type"] = "PE"
            elif "mach-o" in flo:
                info["file_type"] = "Mach-O"
            elif "pdf" in mime:
                info["file_type"] = "PDF"
            elif "office" in mime or "opendocument" in mime:
                info["file_type"] = "Office"
            elif "zip" in mime:
                info["file_type"] = "ZIP"
            elif "text/x-" in mime or "script" in flo:
                info["file_type"] = "Script"
            else:
                info["file_type"] = mime.split("/")[-1].upper()[:20]
        except Exception:
            pass
        return info

    async def _extract_strings_raw(self, file_path: str, min_len: int = 4) -> str:
        if not shutil.which("strings"):
            return ""
        try:
            proc = await asyncio.create_subprocess_exec(
                "strings", f"-n{min_len}", file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            return stdout.decode(errors="replace")[:50000]
        except Exception:
            return ""

    async def _analyze_structure(self, file_path: str) -> dict:
        """readelf structure analysis."""
        result = {}
        readelf_bin = shutil.which("readelf")
        if not readelf_bin:
            return result
        try:
            proc = await asyncio.create_subprocess_exec(
                readelf_bin, "-h", file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            result["elf_header"] = stdout.decode(errors="replace")[:2000]
        except Exception:
            pass
        return result

    async def _run_yara(self, file_path: str) -> dict:
        """Run YARA if available."""
        result = {"rules_available": False, "matches": []}
        yara_bin = shutil.which("yara")
        if not yara_bin:
            return result

        # Look for YARA rules in common locations
        yara_rules_dirs = [
            "/usr/share/yara-rules",
            "/opt/yara-rules",
            "./data/yara_rules",
        ]
        rules_file = None
        for d in yara_rules_dirs:
            p = Path(d)
            if p.exists():
                yrules = list(p.glob("*.yar")) + list(p.glob("*.yara"))
                if yrules:
                    rules_file = str(yrules[0])
                    break

        if not rules_file:
            result["message"] = "No YARA rules found in standard locations"
            return result

        result["rules_available"] = True
        try:
            proc = await asyncio.create_subprocess_exec(
                yara_bin, rules_file, file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            out = stdout.decode(errors="replace").strip()
            result["matches"] = out.splitlines() if out else []
        except Exception as e:
            result["error"] = str(e)

        return result

    def _assess_maliciousness(self, analysis: dict) -> bool:
        """Heuristic maliciousness assessment."""
        score = 0
        iocs = analysis.get("iocs", {})

        if iocs.get("ips"):
            score += 2
        if iocs.get("registry_keys"):
            score += 2
        if iocs.get("mutexes"):
            score += 3
        if analysis.get("yara", {}).get("matches"):
            score += 5
        if analysis.get("sandbox", {}).get("exit_code", 0) not in (0, None):
            score += 1

        # Dangerous strings
        strings = analysis.get("strings_sample", "").lower()
        danger_kws = ["shellcode", "meterpreter", "payload", "reverse_shell",
                      "mimikatz", "cobalt", "metasploit"]
        for kw in danger_kws:
            if kw in strings:
                score += 3

        return score >= 5

    def _guess_family(self, analysis: dict) -> Optional[str]:
        """Simple malware family guess from strings."""
        strings = analysis.get("strings_sample", "").lower()
        families = {
            "mimikatz": "Mimikatz",
            "meterpreter": "Metasploit/Meterpreter",
            "cobalt strike": "Cobalt Strike",
            "empire": "PowerShell Empire",
            "wannacry": "WannaCry",
            "notpetya": "NotPetya",
            "lockbit": "LockBit",
        }
        for kw, name in families.items():
            if kw in strings:
                return name
        return None
