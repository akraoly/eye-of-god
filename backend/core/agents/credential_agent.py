"""
CredentialAgent — Module 9.

Hash identification, cracking (hashcat), Kerbrute, CME validation,
pattern analysis, encrypted credential storage.
All external tool calls use asyncio.create_subprocess_exec.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import uuid
import logging
from datetime import datetime
from typing import Optional

from core.security.fernet_enc import encrypt, decrypt

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 120) -> tuple[str, bool]:
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


def _tool_missing(name: str) -> dict:
    return {"available": False, "error": "tool_not_found", "tool": name}


# ── Hash patterns for identification ──────────────────────────────────────────

HASH_PATTERNS = [
    # (regex, hashcat_mode, name, description)
    (r"^[a-f0-9]{32}$",        "0",     "MD5",           "MD5 (32 hex chars)"),
    (r"^\$1\$.{8}\$.{22}$",    "500",   "MD5-Crypt",     "MD5-Crypt Unix shadow"),
    (r"^[a-f0-9]{40}$",        "100",   "SHA1",          "SHA-1 (40 hex chars)"),
    (r"^[a-f0-9]{56}$",        "700",   "SHA-224",       "SHA-224 (56 hex chars)"),
    (r"^[a-f0-9]{64}$",        "1400",  "SHA-256",       "SHA-256 (64 hex chars)"),
    (r"^[a-f0-9]{96}$",        "10800", "SHA-384",       "SHA-384 (96 hex chars)"),
    (r"^[a-f0-9]{128}$",       "1700",  "SHA-512",       "SHA-512 (128 hex chars)"),
    (r"^\$2[aby]\$.{56}$",     "3200",  "bcrypt",        "bcrypt (60 chars)"),
    (r"^\$5\$.{8,16}\$.{43}$", "7400",  "SHA-256-Crypt", "SHA-256-Crypt Unix shadow"),
    (r"^\$6\$.{8,16}\$.{86}$", "1800",  "SHA-512-Crypt", "SHA-512-Crypt Unix shadow"),
    (r"^[a-f0-9]{32}:[a-f0-9]{32}$", "3100", "Oracle-H", "Oracle H: Type (pre-11G)"),
    (r"^[A-Z0-9]{32}$",        "1000",  "NTLM",          "Windows NTLM"),
    (r"^[a-f0-9]{32}:[a-f0-9]{32}$", "5500", "NetNTLMv1", "NetNTLMv1"),
    (r"^[a-zA-Z0-9+/]{45}={1,2}$",   "1500", "DES-Crypt", "DES-Crypt (13 chars)"),
    (r"^\$apr1\$.{8}\$.{22}$", "1600",  "APR1-MD5",      "Apache MD5-APR1"),
    (r"^[a-f0-9]{16}$",        "3000",  "LM",            "Windows LM (16 hex)"),
    (r"^\$P\$.{31}$",          "400",   "phpass",        "phpass (WordPress/phpBB)"),
    (r"^\$H\$.{31}$",          "400",   "phpass",        "phpass variant"),
    (r"^[a-f0-9]{32}:[a-zA-Z0-9]{16}$", "10", "MD5-Salt", "md5($pass.$salt)"),
    (r"^\{SSHA\}",             "111",   "SSHA",          "LDAP SSHA"),
    (r"^\{SHA\}",              "101",   "SHA-Base64",    "LDAP SHA base64"),
    (r"^[a-zA-Z0-9]{43}=$",    "8900",  "scrypt",        "scrypt"),
    (r"^\$argon2",             "21900", "Argon2",        "Argon2d/Argon2id"),
    (r"^pbkdf2_sha",           "10000", "PBKDF2-SHA256", "Django PBKDF2-SHA256"),
    (r"^[a-f0-9]{32}::::",     "5500",  "NetNTLMv1",     "NetNTLMv1 full"),
    (r"^:::.+::",              "5600",  "NetNTLMv2",     "NetNTLMv2"),
]


class CredentialAgent:
    """
    Credential cracking, validation, and encrypted storage agent.
    """

    # ── Hash identification ────────────────────────────────────────────────────

    async def identify_hash(self, hash_str: str) -> dict:
        """Identify hash type using pattern matching + hashid/hash-identifier."""
        hash_str = hash_str.strip()
        matches = []

        # Pattern-based identification
        for pattern, mode, name, desc in HASH_PATTERNS:
            if re.match(pattern, hash_str, re.IGNORECASE):
                matches.append({
                    "name": name,
                    "hashcat_mode": mode,
                    "description": desc,
                    "confidence": "high",
                })

        # hashid tool
        if shutil.which("hashid"):
            out, ok = await _run(["hashid", "-m", hash_str], timeout=15)
            if ok:
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("[+]"):
                        # Format: [+] Name [Hashcat Mode: XXXX]
                        name_part = re.sub(r"\s*\[.*?\]", "", line[3:]).strip()
                        mode_match = re.search(r"Hashcat Mode:\s*(\d+)", line)
                        hmode = mode_match.group(1) if mode_match else "?"
                        # Only add if not already in matches
                        if not any(m["name"] == name_part for m in matches):
                            matches.append({
                                "name": name_part,
                                "hashcat_mode": hmode,
                                "description": f"hashid: {name_part}",
                                "confidence": "medium",
                                "source": "hashid",
                            })

        # hash-identifier (interactive - pipe input)
        if not matches and shutil.which("hash-identifier"):
            proc = await asyncio.create_subprocess_exec(
                "hash-identifier",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(input=(hash_str + "\n\n").encode()),
                    timeout=10,
                )
                out = stdout.decode("utf-8", errors="replace")
                for line in out.splitlines():
                    if "Possible Hashs:" in line or "Least Possible Hashs:" in line:
                        continue
                    if line.strip().startswith("[+]"):
                        name_part = line.strip()[3:].strip()
                        matches.append({
                            "name": name_part,
                            "hashcat_mode": "?",
                            "description": f"hash-identifier: {name_part}",
                            "confidence": "low",
                            "source": "hash-identifier",
                        })
            except asyncio.TimeoutError:
                pass

        return {
            "hash": hash_str[:80],
            "length": len(hash_str),
            "matches": matches,
            "best_guess": matches[0] if matches else None,
        }

    # ── Crack hash ────────────────────────────────────────────────────────────

    async def crack_hash(
        self,
        hash_str: str,
        hash_type: str,
        wordlist: str = "/usr/share/wordlists/rockyou.txt",
        rules: str = None,
    ) -> dict:
        """
        Launch hashcat to crack a single hash.
        hash_type: hashcat mode number (e.g. "0" for MD5, "1000" for NTLM)
        """
        if not shutil.which("hashcat"):
            return _tool_missing("hashcat")

        if not os.path.exists(wordlist):
            return {
                "available": True,
                "success": False,
                "error": f"Wordlist not found: {wordlist}",
                "hint": "Install rockyou: sudo gzip -d /usr/share/wordlists/rockyou.txt.gz",
            }

        # Write hash to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hash", delete=False) as f:
            f.write(hash_str.strip() + "\n")
            hash_file = f.name

        pot_file = hash_file + ".pot"

        cmd = [
            "hashcat",
            "-m", str(hash_type),
            "-a", "0",           # dictionary attack
            "--quiet",
            "--potfile-path", pot_file,
            hash_file,
            wordlist,
        ]

        if rules:
            cmd += ["-r", rules]

        try:
            out, ok = await _run(cmd, timeout=300)

            # Check potfile for cracked result
            cracked = None
            if os.path.exists(pot_file):
                with open(pot_file) as pf:
                    content = pf.read().strip()
                    if content:
                        # Format: hash:password
                        parts = content.split(":", 1)
                        if len(parts) == 2:
                            cracked = parts[1]

            # Also check hashcat --show output
            if not cracked:
                show_out, _ = await _run(
                    ["hashcat", "-m", str(hash_type), "--show",
                     "--potfile-path", pot_file, hash_file],
                    timeout=15,
                )
                for line in show_out.splitlines():
                    if ":" in line:
                        cracked = line.split(":", 1)[1].strip()
                        break

            return {
                "available": True,
                "success": cracked is not None,
                "hash": hash_str[:80],
                "hash_type": hash_type,
                "wordlist": wordlist,
                "cracked": cracked,
                "cracked_at": datetime.utcnow().isoformat() if cracked else None,
                "output": out[:1000],
            }
        finally:
            for p in [hash_file, pot_file]:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    # ── Crack hash file ───────────────────────────────────────────────────────

    async def crack_file(self, hash_file: str, hash_type: str,
                         wordlist: str = "/usr/share/wordlists/rockyou.txt") -> dict:
        """Crack multiple hashes from a file."""
        if not shutil.which("hashcat"):
            return _tool_missing("hashcat")

        if not os.path.exists(hash_file):
            return {"available": True, "success": False, "error": f"Hash file not found: {hash_file}"}

        if not os.path.exists(wordlist):
            return {"available": True, "success": False, "error": f"Wordlist not found: {wordlist}"}

        import tempfile
        pot_file = hash_file + ".pot"

        cmd = [
            "hashcat",
            "-m", str(hash_type),
            "-a", "0",
            "--quiet",
            "--potfile-path", pot_file,
            hash_file,
            wordlist,
        ]

        out, ok = await _run(cmd, timeout=600)

        # Parse cracked from potfile
        cracked_list = []
        if os.path.exists(pot_file):
            with open(pot_file) as pf:
                for line in pf.read().strip().splitlines():
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        cracked_list.append({"hash": parts[0], "password": parts[1]})

        return {
            "available": True,
            "success": True,
            "hash_file": hash_file,
            "hash_type": hash_type,
            "cracked_count": len(cracked_list),
            "cracked": cracked_list,
            "output": out[:2000],
        }

    # ── Kerbrute ──────────────────────────────────────────────────────────────

    async def kerbrute(
        self,
        domain: str,
        dc_ip: str,
        userlist: str,
        mode: str = "userenum",
    ) -> dict:
        """
        Run kerbrute.
        Modes: userenum | bruteuser | passwordspray | bruteforce
        """
        if not shutil.which("kerbrute"):
            return _tool_missing("kerbrute")

        if not os.path.exists(userlist):
            return {
                "available": True,
                "success": False,
                "error": f"User list not found: {userlist}",
            }

        cmd = [
            "kerbrute",
            mode,
            "--dc", dc_ip,
            "--domain", domain,
            userlist,
        ]

        out, ok = await _run(cmd, timeout=180)

        # Parse valid users from output
        valid_users = []
        for line in out.splitlines():
            if "VALID USERNAME" in line or "VALID USER" in line:
                # Extract username from line
                m = re.search(r"VALID\s+USER\w*:\s+(.+)", line, re.IGNORECASE)
                if m:
                    valid_users.append(m.group(1).strip())

        valid_creds = []
        for line in out.splitlines():
            if "VALID LOGIN" in line:
                m = re.search(r"VALID\s+LOGIN:\s+(.+):(.+)", line, re.IGNORECASE)
                if m:
                    valid_creds.append({"username": m.group(1).strip(), "password": m.group(2).strip()})

        return {
            "available": True,
            "success": ok,
            "domain": domain,
            "dc_ip": dc_ip,
            "mode": mode,
            "userlist": userlist,
            "valid_users": valid_users,
            "valid_credentials": valid_creds,
            "output": out[:4000],
        }

    # ── CrackMapExec validation ───────────────────────────────────────────────

    async def validate_credentials(
        self,
        target: str,
        username: str,
        password: str,
        protocol: str = "smb",
    ) -> dict:
        """
        Validate credentials using CrackMapExec.
        Protocols: smb | winrm | ssh | ldap | mssql | rdp
        """
        # Try cme or crackmapexec
        cme_bin = shutil.which("cme") or shutil.which("crackmapexec")
        if not cme_bin:
            return _tool_missing("crackmapexec/cme")

        cmd = [
            cme_bin,
            protocol,
            target,
            "-u", username,
            "-p", password,
        ]

        out, ok = await _run(cmd, timeout=60)

        # Parse result: "[+]" = valid, "[-]" = invalid, "(Pwn3d!)" = admin
        is_valid = False
        is_admin = False
        status = "invalid"

        for line in out.splitlines():
            if "[+]" in line:
                is_valid = True
                status = "valid"
            if "Pwn3d!" in line or "pwn3d" in line.lower():
                is_admin = True
                status = "admin"
            if "[-]" in line and "STATUS_" in line:
                status = "locked_or_expired"

        return {
            "available": True,
            "success": True,
            "target": target,
            "username": username,
            "protocol": protocol,
            "is_valid": is_valid,
            "is_admin": is_admin,
            "status": status,
            "output": out[:2000],
        }

    # ── Password pattern analysis ─────────────────────────────────────────────

    async def analyze_password_patterns(self, cracked_passwords: list) -> dict:
        """
        Analyze cracked passwords to find patterns and build a targeted wordlist.
        """
        if not cracked_passwords:
            return {"error": "No passwords provided"}

        total = len(cracked_passwords)
        analysis: dict = {
            "total": total,
            "patterns": {},
            "length_distribution": {},
            "charset_distribution": {
                "lowercase_only": 0,
                "uppercase_only": 0,
                "mixed_case": 0,
                "digits_only": 0,
                "alphanumeric": 0,
                "with_special": 0,
            },
            "common_patterns": [],
            "custom_rules": [],
        }

        lengths = {}
        base_words = {}

        for pwd in cracked_passwords:
            pwd = str(pwd)
            # Length distribution
            l = len(pwd)
            lengths[l] = lengths.get(l, 0) + 1

            # Charset analysis
            has_lower = bool(re.search(r"[a-z]", pwd))
            has_upper = bool(re.search(r"[A-Z]", pwd))
            has_digit = bool(re.search(r"\d", pwd))
            has_special = bool(re.search(r"[^a-zA-Z0-9]", pwd))

            if has_special:
                analysis["charset_distribution"]["with_special"] += 1
            elif has_digit and (has_lower or has_upper):
                analysis["charset_distribution"]["alphanumeric"] += 1
            elif has_upper and has_lower:
                analysis["charset_distribution"]["mixed_case"] += 1
            elif has_upper and not has_lower:
                analysis["charset_distribution"]["uppercase_only"] += 1
            elif has_lower and not has_upper:
                analysis["charset_distribution"]["lowercase_only"] += 1
            elif has_digit and not has_lower and not has_upper:
                analysis["charset_distribution"]["digits_only"] += 1

            # Extract base word (strip trailing digits/symbols)
            base = re.sub(r"[^a-zA-Z]+$", "", pwd)
            if base and len(base) >= 3:
                base_words[base.lower()] = base_words.get(base.lower(), 0) + 1

            # Common pattern detection
            if re.match(r"^[A-Z][a-z]+\d+[!@#$%]?$", pwd):
                analysis["patterns"]["Word+Numbers"] = analysis["patterns"].get("Word+Numbers", 0) + 1
            if re.match(r"^\d+$", pwd):
                analysis["patterns"]["Numbers only"] = analysis["patterns"].get("Numbers only", 0) + 1
            if re.match(r"^[a-z]+$", pwd):
                analysis["patterns"]["Lowercase word"] = analysis["patterns"].get("Lowercase word", 0) + 1
            if re.search(r"(password|pass|123|qwerty|admin|letmein)", pwd, re.IGNORECASE):
                analysis["patterns"]["Common weak"] = analysis["patterns"].get("Common weak", 0) + 1
            if re.search(r"(19|20)\d{2}$", pwd):
                analysis["patterns"]["Word+Year"] = analysis["patterns"].get("Word+Year", 0) + 1

        analysis["length_distribution"] = {str(k): v for k, v in sorted(lengths.items())}
        analysis["average_length"] = (
            round(sum(int(k) * v for k, v in lengths.items()) / total, 1)
            if total else 0
        )
        analysis["most_common_length"] = (
            max(lengths.items(), key=lambda x: x[1])[0] if lengths else 0
        )

        # Top base words
        analysis["top_base_words"] = sorted(
            [{"word": k, "count": v} for k, v in base_words.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:20]

        # Generate hashcat rules based on patterns
        rules = []
        if analysis["patterns"].get("Word+Numbers"):
            rules.append("$1 $2 $3  # Append 123")
            rules.append("Az\"[0-9]\"  # Append single digit")
        if analysis["patterns"].get("Word+Year"):
            rules += ["$2 $0 $2 $3", "$2 $0 $2 $4"]  # Append 2023, 2024
        if analysis["charset_distribution"]["mixed_case"]:
            rules.append("c  # Capitalize first letter")
            rules.append("u  # Uppercase all")
        if analysis["charset_distribution"]["with_special"]:
            rules += ["$!", "$@", "$#", "$1 $!"]

        analysis["custom_rules"] = list(set(rules))
        analysis["recommendations"] = [
            f"Most common length: {analysis['most_common_length']} chars",
            f"Generate variants of top base words using identified patterns",
            f"Use hashcat rules: {', '.join(rules[:3]) if rules else 'None identified'}",
        ]

        return analysis

    # ── Store credential ──────────────────────────────────────────────────────

    async def store_credential(
        self,
        target: str,
        username: str,
        password_or_hash: str,
        source: str,
        hash_type: str = None,
        is_valid: bool = False,
    ) -> str:
        """Store a credential encrypted with Fernet. Returns cred_id."""
        cred_id = str(uuid.uuid4())
        try:
            # Encrypt password/hash
            encrypted = encrypt(password_or_hash)

            # Detect if it's a hash or plaintext
            is_hash = bool(re.match(r"^[a-f0-9]{32,128}$", password_or_hash, re.IGNORECASE))

            from database.db import SessionLocal
            from database.models import CrackedCredential
            with SessionLocal() as db:
                cred = CrackedCredential(
                    cred_id=cred_id,
                    target=target,
                    username=username,
                    password_enc=encrypted,
                    hash_value=password_or_hash if is_hash else None,
                    hash_type=hash_type,
                    source=source,
                    cracked_at=datetime.utcnow(),
                    is_valid=is_valid,
                )
                db.add(cred)
                db.commit()
                logger.info("Credential stored: %s@%s (source: %s)", username, target, source)
        except Exception as exc:
            logger.error("store_credential error: %s", exc)

        return cred_id

    # ── List credentials ──────────────────────────────────────────────────────

    async def list_credentials(self, target: str = None) -> list:
        """
        List stored credentials (passwords masked except first 2 chars).
        """
        try:
            from database.db import SessionLocal
            from database.models import CrackedCredential
            with SessionLocal() as db:
                query = db.query(CrackedCredential)
                if target:
                    query = query.filter(CrackedCredential.target == target)
                creds = query.order_by(CrackedCredential.cracked_at.desc()).all()
                result = []
                for c in creds:
                    # Mask password
                    try:
                        plain = decrypt(c.password_enc)
                        masked = plain[:2] + "*" * max(0, len(plain) - 2)
                    except Exception:
                        masked = "***"

                    result.append({
                        "cred_id": c.cred_id,
                        "target": c.target,
                        "username": c.username,
                        "password_masked": masked,
                        "hash_type": c.hash_type,
                        "source": c.source,
                        "is_valid": c.is_valid,
                        "cracked_at": c.cracked_at.isoformat() if c.cracked_at else None,
                    })
                return result
        except Exception as exc:
            logger.error("list_credentials error: %s", exc)
            return []

    async def get_credential_plaintext(self, cred_id: str) -> Optional[str]:
        """Retrieve and decrypt a stored credential (use carefully)."""
        try:
            from database.db import SessionLocal
            from database.models import CrackedCredential
            with SessionLocal() as db:
                cred = db.query(CrackedCredential).filter_by(cred_id=cred_id).first()
                if not cred:
                    return None
                return decrypt(cred.password_enc)
        except Exception as exc:
            logger.error("get_credential_plaintext error: %s", exc)
            return None
