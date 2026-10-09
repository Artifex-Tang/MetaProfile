#!/usr/bin/env python3
"""Probe new cloud host: SSH, docker, disk, ports. Reads deploy/cloud/.env."""
import os, sys, paramiko
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load .env (simple parse, ignore comments/blanks)
env = {}
envpath = Path("deploy/cloud/.env")
for line in envpath.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip()

host = env["SSH_HOST"]; port = int(env.get("SSH_PORT", "22"))
user = env["SSH_USER"]; pwd = env["SSH_PASSWORD"]

print(f"=== connect {user}@{host}:{port} ===")
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(host, port=port, username=user, password=pwd, timeout=20)
print("SSH OK")

def run(cmd, label=None):
    if label:
        print(f"--- {label} ---")
    _in, out, err = cli.exec_command(cmd, timeout=30)
    o = out.read().decode("utf-8", "replace").rstrip()
    e = err.read().decode("utf-8", "replace").rstrip()
    rc = out.channel.recv_exit_status()
    if o: print(o)
    if e: print(f"[stderr] {e}")
    print(f"[rc={rc}]")
    return rc

run("uname -a; cat /etc/os-release | head -2", "OS")
run("nproc; free -h | head -2", "CPU/MEM")
run("df -h / /data 2>/dev/null; ls -la /data 2>/dev/null || echo 'NO /data'", "DISK")
run("docker --version 2>&1; docker compose version 2>&1; docker ps 2>&1 | head -3", "DOCKER")
run("ls -la /etc/docker/daemon.json 2>/dev/null && cat /etc/docker/daemon.json || echo 'no daemon.json'", "docker data-root")
run("ss -tlnp 2>/dev/null | grep -E ':22|:80|:8000|:7474|:7687' || echo 'ports quiet'", "LISTEN PORTS")
run("docker ps -a 2>/dev/null | head -10 || echo 'no containers'", "EXISTING CONTAINERS")

cli.close()
print("=== probe done ===")
