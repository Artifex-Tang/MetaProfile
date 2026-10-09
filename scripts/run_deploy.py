#!/usr/bin/env python3
"""On host: extract kit, run deploy.sh, stream output."""
import sys, paramiko
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

env = {}
for line in Path("deploy/cloud/.env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
host = env["SSH_HOST"]; port = int(env.get("SSH_PORT", "22"))
user = env["SSH_USER"]; pwd = env["SSH_PASSWORD"]

cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(host, port=port, username=user, password=pwd, timeout=30)

def run(cmd, label=None, timeout=600):
    if label: print(f"--- {label} ---", flush=True)
    _in, out, err = cli.exec_command(cmd, timeout=timeout, get_pty=True)
    # stream
    while True:
        chunk = out.read(4096)
        if not chunk:
            break
        try:
            sys.stdout.write(chunk.decode("utf-8","replace"))
            sys.stdout.flush()
        except Exception:
            pass
    rc = out.channel.recv_exit_status()
    print(f"\n[rc={rc}]")
    return rc

# 1. extract kit
run("cd /root && rm -rf metaprofile-deploy-kit && tar -xzf metaprofile-deploy-kit.tar.gz && ls -la metaprofile-deploy-kit/",
    "extract kit", timeout=180)

# 2. run deploy.sh (uses default PG_PASSWORD=metaprofile NEO4J_PASSWORD=password)
run("cd /root/metaprofile-deploy-kit && bash deploy.sh",
    "deploy.sh (7 steps)", timeout=900)

cli.close()
print("=== deploy runner done ===")
