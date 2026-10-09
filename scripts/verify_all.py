#!/usr/bin/env python3
"""Final: 4-profile stats via nginx + cleanup tarballs on host."""
import sys, paramiko
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
env = {}
for line in Path("deploy/cloud/.env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
host = env["SSH_HOST"]; port = int(env.get("SSH_PORT","22")); user = env["SSH_USER"]; pwd = env["SSH_PASSWORD"]

# 1. 4 profile stats via nginx (local curl on host → nginx → backend)
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(host, port=port, username=user, password=pwd, timeout=30)
def run(cmd, label=None):
    if label: print(f"--- {label} ---")
    _in, out, err = cli.exec_command(cmd, timeout=30)
    o = out.read().decode("utf-8","replace").rstrip()
    e = err.read().decode("utf-8","replace").rstrip()
    if o: print(o)
    if e: print("[stderr]", e)
    return out.channel.recv_exit_status()
for T in ["tech","project","org","person"]:
    run(f"curl -s http://localhost/api-{T}/api/v1/stats/{T} | head -c 120", f"stats/{T}")
run("docker compose -f /data/deploy/docker-compose.readonly.yml ps --format 'table {{{{.Name}}}}\t{{{{.Status}}}}' 2>/dev/null || docker ps --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'", "containers")
# 2. cleanup tarballs (images already loaded to /data/docker)
run("rm -f /root/metaprofile-deploy-kit.tar.gz /root/mp-all-images.tar.gz && df -h / /data", "cleanup tarballs + disk")
cli.close()
print("=== verify+cleanup done ===")
