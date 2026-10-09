#!/usr/bin/env python3
"""Run deploy.sh from /root (kit files already extracted flat there)."""
import sys, paramiko
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
env = {}
for line in Path("deploy/cloud/.env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
host = env["SSH_HOST"]; port = int(env.get("SSH_PORT","22")); user = env["SSH_USER"]; pwd = env["SSH_PASSWORD"]
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(host, port=port, username=user, password=pwd, timeout=30)

cmd = "cd /root && bash deploy.sh"
print(f"--- {cmd} ---", flush=True)
_in, out, err = cli.exec_command(cmd, timeout=900, get_pty=True)
while True:
    chunk = out.read(4096)
    if not chunk: break
    sys.stdout.write(chunk.decode("utf-8","replace")); sys.stdout.flush()
rc = out.channel.recv_exit_status()
print(f"\n[rc={rc}]")
cli.close()
print("=== deploy done ===")
