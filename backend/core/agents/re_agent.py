"""
REAgent — AI-assisted reverse engineering using Ghidra headless + local tools.
Analyzes ELF/PE/Mach-O binaries: checksec, strings, symbols, decompilation, Claude analysis.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from core.tools.logger import get_logger

logger = get_logger("re_agent")


class REAgent:
    """AI-assisted reverse engineering. Uses Ghidra headless for decompilation."""

    GHIDRA_PATH     = "/usr/bin/ghidra"
    GHIDRA_HEADLESS = "/usr/share/ghidra/support/analyzeHeadless"
    WORK_DIR        = Path("./data/re_workspace")

    DANGEROUS_SINKS = [
        "strcpy", "strcat", "sprintf", "vsprintf", "gets", "scanf",
        "memcpy", "memmove", "strncpy", "strncat", "snprintf",
        "system", "popen", "execve", "execl", "execlp", "execvp",
        "dlopen", "LoadLibrary", "CreateProcess",
    ]

    def __init__(self):
        self.WORK_DIR.mkdir(parents=True, exist_ok=True)

    # ── Main Analysis Pipeline ────────────────────────────────────────────────

    async def analyze_binary(self, binary_path: str, binary_name: Optional[str] = None) -> dict:
        """
        Full binary analysis pipeline:
        1. file(1) — detect format (ELF/PE/Mach-O)
        2. checksec — protection flags
        3. strings extraction
        4. nm/objdump — symbols
        5. Ghidra headless decompilation (if available)
        6. Claude analysis of decompiled code
        """
        path = Path(binary_path)
        if not path.exists():
            return {"error": f"File not found: {binary_path}"}

        binary_name = binary_name or path.name
        logger.info(f"[REAgent] Analyzing {binary_name}...")

        result: dict = {
            "binary_name": binary_name,
            "binary_path": binary_path,
            "analysis_id": str(uuid.uuid4())[:8],
        }

        # 1. File type detection
        file_info = await self._detect_file_type(binary_path)
        result.update(file_info)

        # 2. Hash calculation
        result["hashes"] = self._calculate_hashes(binary_path)

        # 3. Checksec
        checksec = await self.run_checksec(binary_path)
        result["protections"] = checksec

        # 4. Strings
        strings = await self.extract_strings(binary_path)
        result["strings"] = strings
        result["strings_count"] = len(strings.get("all", []))

        # 5. Symbols
        symbols = await self.get_symbols(binary_path)
        result["symbols"] = symbols
        result["functions_count"] = len(symbols.get("functions", []))

        # 6. Imports/Exports
        ie = await self.extract_imports_exports(binary_path)
        result["imports_exports"] = ie

        # 7. Ghidra decompilation
        ghidra_available = shutil.which(self.GHIDRA_HEADLESS) is not None or Path(self.GHIDRA_HEADLESS).exists()
        result["ghidra_available"] = ghidra_available

        decompiled = {}
        if ghidra_available:
            project_name = f"re_{result['analysis_id']}"
            decompiled = await self.run_ghidra_headless(binary_path, project_name)
            result["ghidra_output"] = decompiled

        # 8. Claude analysis
        code_sample = decompiled.get("functions_text", "") or self._build_code_sample(result)
        if code_sample:
            claude_analysis = await self.analyze_with_claude(code_sample, result)
            result["claude_analysis"] = claude_analysis
            result["vulnerabilities"] = claude_analysis.get("vulnerabilities", [])

        # 9. Quick danger check in strings/imports
        quick_vulns = self._quick_vuln_scan(result)
        if quick_vulns and not result.get("vulnerabilities"):
            result["vulnerabilities"] = quick_vulns

        result["status"] = "completed"
        logger.info(f"[REAgent] Analysis of {binary_name} completed.")
        return result

    # ── File type detection ───────────────────────────────────────────────────

    async def _detect_file_type(self, binary_path: str) -> dict:
        info = {"file_type": "unknown", "arch": "unknown", "os": "unknown"}

        if not shutil.which("file"):
            return info

        try:
            proc = await asyncio.create_subprocess_exec(
                "file", "-b", binary_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            file_out = stdout.decode(errors="replace").strip()
            info["file_type_raw"] = file_out

            flo = file_out.lower()
            if "elf" in flo:
                info["file_type"] = "ELF"
                info["os"] = "Linux"
            elif "pe32" in flo or "portable executable" in flo:
                info["file_type"] = "PE"
                info["os"] = "Windows"
            elif "mach-o" in flo:
                info["file_type"] = "Mach-O"
                info["os"] = "macOS"
            elif "script" in flo or "python" in flo:
                info["file_type"] = "script"
            else:
                info["file_type"] = file_out[:50]

            for arch_kw in ("x86-64", "amd64", "x86_64"):
                if arch_kw in flo:
                    info["arch"] = "x86_64"
                    break
            else:
                if "i386" in flo or "80386" in flo:
                    info["arch"] = "x86"
                elif "arm" in flo:
                    info["arch"] = "ARM64" if "64" in flo else "ARM"
                elif "mips" in flo:
                    info["arch"] = "MIPS"
        except Exception as e:
            logger.debug(f"file(1) failed: {e}")

        return info

    # ── Hashes ────────────────────────────────────────────────────────────────

    def _calculate_hashes(self, binary_path: str) -> dict:
        hashes = {}
        try:
            data = Path(binary_path).read_bytes()
            hashes["md5"]    = hashlib.md5(data).hexdigest()
            hashes["sha1"]   = hashlib.sha1(data).hexdigest()
            hashes["sha256"] = hashlib.sha256(data).hexdigest()
            hashes["size"]   = len(data)
        except Exception as e:
            hashes["error"] = str(e)
        return hashes

    # ── Checksec ─────────────────────────────────────────────────────────────

    async def run_checksec(self, binary_path: str) -> dict:
        """checksec --file=binary."""
        result = {
            "nx": "unknown", "pie": "unknown", "canary": "unknown",
            "relro": "unknown", "fortify": "unknown", "aslr": "unknown",
        }

        checksec_bin = shutil.which("checksec")
        if not checksec_bin:
            # Try pwn python module
            return await self.identify_protections(binary_path)

        try:
            proc = await asyncio.create_subprocess_exec(
                checksec_bin, f"--file={binary_path}", "--output=json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
            out = stdout.decode(errors="replace").strip()

            if out.startswith("{"):
                data = json.loads(out)
                # checksec JSON format varies by version
                for key, val in data.items():
                    if isinstance(val, dict):
                        result.update({k.lower(): v for k, v in val.items()})
                    elif key.lower() in result:
                        result[key.lower()] = val
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"checksec failed: {e}")
            return await self.identify_protections(binary_path)

        return result

    # ── Strings ───────────────────────────────────────────────────────────────

    async def extract_strings(self, binary_path: str, min_len: int = 4) -> dict:
        """strings command + categorize (IPs, URLs, keys, paths)."""
        result: dict = {"all": [], "ips": [], "urls": [], "paths": [], "interesting": []}

        strings_bin = shutil.which("strings")
        if not strings_bin:
            return result

        try:
            proc = await asyncio.create_subprocess_exec(
                strings_bin, f"-n{min_len}", binary_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            lines = stdout.decode(errors="replace").splitlines()
        except Exception as e:
            logger.debug(f"strings failed: {e}")
            return result

        import re
        ip_re   = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
        url_re  = re.compile(r"https?://[^\s\"'<>]+")
        path_re = re.compile(r"(/[a-zA-Z0-9._\-/]{4,}|[A-Za-z]:\\[^\s\"]{4,})")

        interesting_kws = [
            "password", "passwd", "secret", "key", "token", "api", "credential",
            "admin", "root", "exec", "shell", "cmd", "SELECT", "INSERT", "DROP",
        ]

        result["all"] = lines[:2000]  # cap

        for line in lines:
            if ip_re.search(line):
                result["ips"].append(line)
            if url_re.search(line):
                result["urls"].append(line)
            if path_re.search(line):
                result["paths"].append(line[:120])
            for kw in interesting_kws:
                if kw.lower() in line.lower() and len(line) > 4:
                    result["interesting"].append(line[:120])
                    break

        # Deduplicate
        for key in ("ips", "urls", "paths", "interesting"):
            result[key] = list(dict.fromkeys(result[key]))[:200]

        return result

    # ── Symbols ───────────────────────────────────────────────────────────────

    async def get_symbols(self, binary_path: str) -> dict:
        """nm + objdump --dynamic-syms."""
        result: dict = {"functions": [], "imports": [], "exports": [], "nm_raw": ""}

        nm_bin = shutil.which("nm")
        if nm_bin:
            try:
                proc = await asyncio.create_subprocess_exec(
                    nm_bin, "--demangle", binary_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
                nm_out = stdout.decode(errors="replace")
                result["nm_raw"] = nm_out[:5000]

                for line in nm_out.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        sym_type = parts[1]
                        sym_name = parts[2]
                        if sym_type in ("T", "t"):
                            result["functions"].append(sym_name)
                        elif sym_type == "U":
                            result["imports"].append(sym_name)
            except Exception as e:
                logger.debug(f"nm failed: {e}")

        objdump_bin = shutil.which("objdump")
        if objdump_bin:
            try:
                proc = await asyncio.create_subprocess_exec(
                    objdump_bin, "--dynamic-syms", binary_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
                dyn_out = stdout.decode(errors="replace")
                result["objdump_dynamic"] = dyn_out[:3000]
            except Exception as e:
                logger.debug(f"objdump failed: {e}")

        return result

    # ── Ghidra headless ───────────────────────────────────────────────────────

    async def run_ghidra_headless(self, binary_path: str, project_name: str) -> dict:
        """
        Run Ghidra headless analysis:
        analyzeHeadless /tmp/ghidra_proj ProjectName -import binary -postScript ExtractFunctions.java
        """
        result: dict = {"status": "not_run", "functions_text": "", "output": ""}

        headless = self.GHIDRA_HEADLESS
        if not (shutil.which(headless) or Path(headless).exists()):
            result["status"] = "ghidra_unavailable"
            return result

        project_dir = Path(tempfile.mkdtemp(prefix="ghidra_"))
        output_dir  = project_dir / "output"
        output_dir.mkdir(exist_ok=True)

        try:
            cmd = [
                headless,
                str(project_dir),
                project_name,
                "-import", binary_path,
                "-deleteProject",
                "-analysisTimeoutPerFile", "120",
                "-log", str(project_dir / "ghidra.log"),
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "JAVA_HOME": os.environ.get("JAVA_HOME", "/usr")},
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)

            out = stdout.decode(errors="replace")
            err = stderr.decode(errors="replace")
            result["output"]    = (out + err)[:5000]
            result["exit_code"] = proc.returncode

            if proc.returncode == 0:
                result["status"] = "success"
                # Try to find any output files
                for f in output_dir.glob("*.c"):
                    result["functions_text"] = f.read_text(errors="replace")[:20000]
                    break
            else:
                result["status"] = "failed"
                result["error"]  = err[:1000]

        except asyncio.TimeoutError:
            result["status"] = "timeout"
            result["error"]  = "Ghidra analysis timed out after 180s"
        except Exception as e:
            result["status"] = "error"
            result["error"]  = str(e)
        finally:
            # Cleanup temp project
            try:
                import shutil as _shutil
                _shutil.rmtree(str(project_dir), ignore_errors=True)
            except Exception:
                pass

        return result

    # ── Claude analysis ───────────────────────────────────────────────────────

    async def analyze_with_claude(self, decompiled_code: str, binary_info: dict) -> dict:
        """
        Send decompiled code to Claude for vulnerability analysis.
        Identifies dangerous sinks, vuln patterns, function purposes, and protections.
        """
        result: dict = {
            "vulnerabilities": [],
            "dangerous_sinks": [],
            "function_purposes": [],
            "analysis": "",
        }

        try:
            import anthropic
            from app.config import settings

            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

            binary_summary = (
                f"Binary: {binary_info.get('binary_name', 'unknown')}\n"
                f"Type: {binary_info.get('file_type', 'unknown')} ({binary_info.get('arch', 'unknown')})\n"
                f"Protections: {json.dumps(binary_info.get('protections', {}))}\n"
                f"Interesting strings: {json.dumps(binary_info.get('strings', {}).get('interesting', [])[:10])}\n"
                f"Imports: {json.dumps(binary_info.get('symbols', {}).get('imports', [])[:20])}\n"
            )

            prompt = f"""You are a reverse engineering expert. Analyze this binary:

{binary_summary}

Decompiled/disassembled code (first 3000 chars):
```
{decompiled_code[:3000]}
```

Provide a JSON analysis with:
{{
  "vulnerabilities": [
    {{
      "type": "buffer_overflow|use_after_free|format_string|command_injection|...",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "location": "function or address",
      "description": "...",
      "cvss_score": 0.0
    }}
  ],
  "dangerous_sinks": ["function_name"],
  "function_purposes": ["main: entry point, ...", "sub_1234: ..."],
  "protection_bypass": "notes on bypassing protections",
  "overall_risk": "CRITICAL|HIGH|MEDIUM|LOW",
  "analysis": "brief paragraph summary"
}}

Respond with ONLY valid JSON."""

            message = client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            content = message.content[0].text.strip()

            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            result.update(parsed)

        except Exception as e:
            logger.debug(f"Claude analysis failed: {e}")
            # Fall back to static analysis
            result["vulnerabilities"] = self._quick_vuln_scan(binary_info)
            result["analysis"] = f"Claude analysis unavailable: {e}. Static scan performed."

        return result

    # ── Protection identification ─────────────────────────────────────────────

    async def identify_protections(self, binary_path: str) -> dict:
        """NX, PIE, ASLR, canary, RELRO, FORTIFY — via readelf."""
        result = {
            "nx": "unknown", "pie": "unknown", "canary": "unknown",
            "relro": "unknown", "fortify": "unknown",
        }

        readelf_bin = shutil.which("readelf")
        if not readelf_bin:
            return result

        try:
            proc = await asyncio.create_subprocess_exec(
                readelf_bin, "-d", binary_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            out = stdout.decode(errors="replace").lower()

            result["nx"]    = "enabled" if "gnu_stack" in out and "rw " not in out else "disabled"
            result["relro"] = "full" if "bind_now" in out else "partial" if "gnu_relro" in out else "none"

        except Exception as e:
            logger.debug(f"readelf failed: {e}")

        # Check for PIE via file output
        try:
            proc = await asyncio.create_subprocess_exec(
                "file", binary_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            out = stdout.decode(errors="replace").lower()
            result["pie"] = "enabled" if "pie executable" in out or "shared object" in out else "disabled"
        except Exception:
            pass

        # Check for stack canary via nm
        try:
            proc = await asyncio.create_subprocess_exec(
                "nm", binary_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            out = stdout.decode(errors="replace")
            result["canary"] = "enabled" if "__stack_chk_fail" in out else "disabled"
            result["fortify"] = "enabled" if "__fortify_fail" in out or "_chk@" in out else "disabled"
        except Exception:
            pass

        return result

    # ── Imports/Exports ───────────────────────────────────────────────────────

    async def extract_imports_exports(self, binary_path: str) -> dict:
        """IAT, EAT for PE; .got/.plt for ELF."""
        result: dict = {"imports": [], "exports": [], "got_plt": []}

        objdump_bin = shutil.which("objdump")
        if not objdump_bin:
            return result

        # PLT for ELF
        try:
            proc = await asyncio.create_subprocess_exec(
                objdump_bin, "--disassemble-section=.plt", binary_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
            plt_out = stdout.decode(errors="replace")
            import re
            plt_funcs = re.findall(r"<([^@>]+)@plt>", plt_out)
            result["got_plt"] = list(set(plt_funcs))
            result["imports"] = list(set(plt_funcs))
        except Exception:
            pass

        return result

    # ── Quick static vulnerability scan ──────────────────────────────────────

    def _quick_vuln_scan(self, analysis: dict) -> list:
        """Scan strings/imports for dangerous patterns without Claude."""
        vulns = []
        imports = analysis.get("symbols", {}).get("imports", []) + analysis.get("imports_exports", {}).get("imports", [])
        interesting = analysis.get("strings", {}).get("interesting", [])

        for sink in self.DANGEROUS_SINKS:
            if any(sink in imp for imp in imports):
                severity = "HIGH" if sink in ("strcpy", "gets", "sprintf", "system", "execve") else "MEDIUM"
                vulns.append({
                    "type": "dangerous_function_use",
                    "severity": severity,
                    "location": "imports",
                    "description": f"Dangerous function '{sink}' found in imports — potential memory/command injection vulnerability",
                    "cvss_score": 7.5 if severity == "HIGH" else 5.0,
                })

        for s in interesting:
            sl = s.lower()
            if "password" in sl and len(s) > 6:
                vulns.append({
                    "type": "hardcoded_credential",
                    "severity": "HIGH",
                    "location": "strings",
                    "description": f"Possible hardcoded password/credential: {s[:60]}",
                    "cvss_score": 7.0,
                })
                break

        return vulns

    def _build_code_sample(self, analysis: dict) -> str:
        """Build a code sample from available analysis data when Ghidra is unavailable."""
        parts = []
        imports = analysis.get("symbols", {}).get("imports", [])
        funcs   = analysis.get("symbols", {}).get("functions", [])
        strings_interesting = analysis.get("strings", {}).get("interesting", [])

        if imports:
            parts.append("/* Imported functions */")
            parts.append("extern " + "; extern ".join(imports[:30]) + ";")
        if funcs:
            parts.append("\n/* Exported/local functions */")
            parts.append("\n".join(f"// function: {f}" for f in funcs[:30]))
        if strings_interesting:
            parts.append("\n/* Interesting strings */")
            parts.append("\n".join(f"// string: {s}" for s in strings_interesting[:20]))

        return "\n".join(parts)
