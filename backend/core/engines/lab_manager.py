"""
LabManager — Module 15
Orchestrates Docker-based vulnerable lab environments.
Each environment is isolated in its own Docker network.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from database.db import SessionLocal
from database.models import LabInstance


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_docker(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Execute docker CLI command, return (rc, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return -1, "", "Timeout"
        return proc.returncode, stdout.decode(errors="replace").strip(), stderr.decode(errors="replace").strip()
    except Exception as e:
        return -1, "", str(e)


def _db_session():
    return SessionLocal()


# ── LabManager ────────────────────────────────────────────────────────────────

class LabManager:
    """
    Orchestrates Docker-based vulnerable lab environments.
    Each environment is isolated in its own Docker network.
    """

    LAB_TEMPLATES: dict = {
        "dvwa": {
            "image": "vulnerables/web-dvwa",
            "ports": {80: None},
            "description": "Damn Vulnerable Web Application",
            "category": "web",
            "env": [],
        },
        "metasploitable2": {
            "image": "tleemcjr/metasploitable2",
            "ports": {21: None, 22: None, 80: None, 139: None, 445: None, 3306: None},
            "description": "Metasploitable 2 — Multiple vulnerabilities",
            "category": "multi",
            "env": [],
        },
        "webgoat": {
            "image": "webgoat/webgoat-8.0",
            "ports": {8080: None},
            "description": "WebGoat — OWASP training",
            "category": "web",
            "env": [],
        },
        "ssh-weak": {
            "image": "rastasheep/ubuntu-sshd",
            "ports": {22: None},
            "description": "Ubuntu SSH with weak password (root:root)",
            "category": "ssh",
            "env": [],
        },
        "ftp-vsftpd": {
            "image": None,
            "dockerfile": (
                "FROM ubuntu:18.04\n"
                "RUN apt-get update && apt-get install -y vsftpd netcat-openbsd\n"
                "RUN echo 'anonymous_enable=YES' >> /etc/vsftpd.conf\n"
                "RUN echo 'local_enable=YES' >> /etc/vsftpd.conf\n"
                "EXPOSE 21\n"
                "CMD [\"vsftpd\", \"/etc/vsftpd.conf\"]\n"
            ),
            "ports": {21: None},
            "description": "vsftpd 2.3.4 backdoor simulation",
            "category": "ftp",
            "env": [],
        },
        "juice-shop": {
            "image": "bkimminich/juice-shop",
            "ports": {3000: None},
            "description": "OWASP Juice Shop — Modern web vulnerabilities",
            "category": "web",
            "env": [],
        },
        "vulhub-struts2": {
            "image": "pyn3rd/struts2-045",
            "ports": {8080: None},
            "description": "Apache Struts2 S2-045 RCE (CVE-2017-5638)",
            "category": "web",
            "env": [],
        },
    }

    def __init__(self):
        if not shutil.which("docker"):
            self._docker_available = False
        else:
            self._docker_available = True

    def _check_docker(self) -> Optional[dict]:
        if not self._docker_available:
            return {"available": False, "message": "docker not found in PATH"}
        return None

    async def create_lab(self, template: str, lab_name: Optional[str] = None) -> dict:
        """
        Spin up Docker container from template:
        1. Create isolated Docker network: docker network create lab_{id}
        2. Run container with --network lab_{id}
        3. Assign random host ports
        4. Register in DB
        Returns: lab_id, ip, exposed_ports
        """
        err = self._check_docker()
        if err:
            return err

        if template not in self.LAB_TEMPLATES:
            return {"error": f"Unknown template '{template}'. Available: {list(self.LAB_TEMPLATES)}"}

        tpl = self.LAB_TEMPLATES[template]
        lab_id = str(uuid.uuid4())
        if not lab_name:
            lab_name = f"{template}-{lab_id[:8]}"

        # Create isolated network
        network_name = f"lab_{lab_id[:12]}"
        rc, net_id, err_msg = await _run_docker(["network", "create", "--driver", "bridge", network_name])
        if rc != 0:
            return {"error": f"Failed to create Docker network: {err_msg}"}

        # Build image from Dockerfile if needed
        image = tpl.get("image")
        if not image:
            build_dir = Path(f"/tmp/lab_{lab_id[:8]}")
            build_dir.mkdir(exist_ok=True)
            (build_dir / "Dockerfile").write_text(tpl["dockerfile"])
            image_tag = f"eyeofgod_lab_{template}:latest"
            rc, _, build_err = await _run_docker(
                ["build", "-t", image_tag, str(build_dir)],
                timeout=300,
            )
            if rc != 0:
                await _run_docker(["network", "rm", network_name])
                return {"error": f"Failed to build image: {build_err}"}
            image = image_tag

        # Compute port mapping
        port_bindings: list[str] = []
        exposed_ports: dict = {}
        base_port = 20000 + (hash(lab_id) % 10000)
        for i, container_port in enumerate(tpl["ports"].keys()):
            host_port = base_port + i
            port_bindings += ["-p", f"127.0.0.1:{host_port}:{container_port}"]
            exposed_ports[str(container_port)] = host_port

        # Env vars
        env_args: list[str] = []
        for e in tpl.get("env", []):
            env_args += ["-e", e]

        # Run container
        container_name = f"lab_{lab_id[:12]}"
        run_cmd = [
            "run", "-d",
            "--name", container_name,
            "--network", network_name,
            "--restart", "no",
            "--cap-drop", "ALL",
            "--cap-add", "NET_BIND_SERVICE",
        ] + port_bindings + env_args + [image]

        rc, container_id, run_err = await _run_docker(run_cmd, timeout=120)
        if rc != 0:
            await _run_docker(["network", "rm", network_name])
            return {"error": f"Failed to start container: {run_err}"}

        container_id = container_id.strip()

        # Get container IP
        rc, ip_json, _ = await _run_docker([
            "inspect",
            "--format",
            "{{json .NetworkSettings.Networks}}",
            container_id,
        ])
        target_ip = "127.0.0.1"
        try:
            nets = json.loads(ip_json)
            for net_data in nets.values():
                if net_data.get("IPAddress"):
                    target_ip = net_data["IPAddress"]
                    break
        except Exception:
            pass

        # Save to DB
        db = _db_session()
        try:
            instance = LabInstance(
                lab_id=lab_id,
                template_name=template,
                lab_name=lab_name,
                container_id=container_id,
                network_id=net_id.strip(),
                target_ip=target_ip,
                exposed_ports=json.dumps(exposed_ports),
                status="running",
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
            )
            db.add(instance)
            db.commit()
        finally:
            db.close()

        return {
            "lab_id": lab_id,
            "lab_name": lab_name,
            "template": template,
            "container_id": container_id[:12],
            "network": network_name,
            "target_ip": target_ip,
            "exposed_ports": exposed_ports,
            "status": "running",
            "message": f"Lab '{template}' started successfully",
        }

    async def list_labs(self) -> list:
        """List all lab instances with status."""
        db = _db_session()
        try:
            instances = (
                db.query(LabInstance)
                .order_by(LabInstance.created_at.desc())
                .all()
            )
            result = []
            for inst in instances:
                # Check live container status
                live_status = inst.status
                if inst.container_id and self._docker_available:
                    rc, state, _ = await _run_docker([
                        "inspect", "--format", "{{.State.Status}}", inst.container_id
                    ], timeout=10)
                    if rc == 0:
                        live_status = state.strip()
                    elif "No such" in state or "No such" in _:
                        live_status = "removed"

                result.append({
                    "lab_id": inst.lab_id,
                    "lab_name": inst.lab_name,
                    "template_name": inst.template_name,
                    "container_id": (inst.container_id or "")[:12],
                    "target_ip": inst.target_ip,
                    "exposed_ports": json.loads(inst.exposed_ports or "{}"),
                    "status": live_status,
                    "created_at": inst.created_at.isoformat() if inst.created_at else None,
                    "last_activity": inst.last_activity.isoformat() if inst.last_activity else None,
                })
            return result
        finally:
            db.close()

    async def stop_lab(self, lab_id: str) -> bool:
        """docker stop + docker rm + docker network rm"""
        err = self._check_docker()
        if err:
            return False

        db = _db_session()
        try:
            inst = db.query(LabInstance).filter_by(lab_id=lab_id).first()
            if not inst:
                return False

            container_id = inst.container_id
            network_id = inst.network_id or f"lab_{lab_id[:12]}"

            if container_id:
                await _run_docker(["stop", "-t", "5", container_id], timeout=30)
                await _run_docker(["rm", "-f", container_id], timeout=30)

            if network_id:
                await _run_docker(["network", "rm", network_id], timeout=30)

            inst.status = "stopped"
            inst.last_activity = datetime.utcnow()
            db.commit()
            return True
        finally:
            db.close()

    async def get_lab_status(self, lab_id: str) -> dict:
        """Check container health."""
        db = _db_session()
        try:
            inst = db.query(LabInstance).filter_by(lab_id=lab_id).first()
            if not inst:
                return {"error": "Lab not found"}

            result = {
                "lab_id": inst.lab_id,
                "lab_name": inst.lab_name,
                "template_name": inst.template_name,
                "target_ip": inst.target_ip,
                "exposed_ports": json.loads(inst.exposed_ports or "{}"),
                "status": inst.status,
                "created_at": inst.created_at.isoformat() if inst.created_at else None,
            }

            if inst.container_id and self._docker_available:
                rc, inspect_json, _ = await _run_docker(
                    ["inspect", inst.container_id], timeout=10
                )
                if rc == 0:
                    try:
                        data = json.loads(inspect_json)
                        if data:
                            state = data[0].get("State", {})
                            result["container_status"] = state.get("Status", "unknown")
                            result["container_running"] = state.get("Running", False)
                            result["started_at"] = state.get("StartedAt", "")
                    except Exception:
                        pass

            return result
        finally:
            db.close()

    async def launch_scan_against_lab(
        self, lab_id: str, scan_type: str = "full"
    ) -> dict:
        """Launch pentest scan against a lab target."""
        db = _db_session()
        try:
            inst = db.query(LabInstance).filter_by(lab_id=lab_id).first()
            if not inst:
                return {"error": "Lab not found"}

            target_ip = inst.target_ip
            exposed_ports = json.loads(inst.exposed_ports or "{}")
            port_list = list(exposed_ports.keys())

            inst.last_activity = datetime.utcnow()
            db.commit()
        finally:
            db.close()

        scan_result: dict = {
            "lab_id": lab_id,
            "target": target_ip,
            "scan_type": scan_type,
            "started_at": datetime.utcnow().isoformat(),
            "results": {},
        }

        if scan_type in ("full", "nmap") and shutil.which("nmap"):
            ports_str = ",".join(port_list) if port_list else "1-1000"
            rc, stdout, _ = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "nmap", "-sV", "-sC", "-p", ports_str, "--open", target_ip,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ).coroutine if hasattr(asyncio, "coroutine") else
                (asyncio.create_subprocess_exec(
                    "nmap", "-sV", "-sC", "-p", ports_str, "--open", target_ip,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )),
                timeout=120,
            )
            scan_result["results"]["nmap"] = "nmap scan requires direct call"

        # Simpler direct call
        if shutil.which("nmap"):
            ports_str = ",".join(str(p) for p in exposed_ports.keys()) if exposed_ports else "1-1000"
            proc = await asyncio.create_subprocess_exec(
                "nmap", "-sV", "-p", ports_str, "--open", target_ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
                scan_result["results"]["nmap"] = stdout_b.decode(errors="replace")
            except asyncio.TimeoutError:
                proc.kill()
                scan_result["results"]["nmap"] = "Timeout"
        else:
            scan_result["results"]["nmap"] = "nmap not available"

        scan_result["completed_at"] = datetime.utcnow().isoformat()
        return scan_result

    async def get_lab_templates(self) -> list:
        """Return available templates with descriptions."""
        templates = []
        for name, tpl in self.LAB_TEMPLATES.items():
            templates.append({
                "name": name,
                "image": tpl.get("image", "custom_build"),
                "description": tpl.get("description", ""),
                "category": tpl.get("category", "unknown"),
                "ports": list(tpl.get("ports", {}).keys()),
                "has_dockerfile": bool(tpl.get("dockerfile")),
            })
        return templates
