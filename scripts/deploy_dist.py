#!/usr/bin/env python3
"""Package frontend/dist + scp to host /data/dist + extract. nginx auto-serves (no restart)."""
import sys, os, paramiko
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
env = {}
for line in Path("deploy/cloud/.env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
host = env["SSH_HOST"]; port = int(env.get("SSH_PORT","22")); user = env["SSH_USER"]; pwd = env["SSH_PASSWORD"]

# 1. package dist
import tarfile, io
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tar:
    tar.add("frontend/dist", arcname=".", recursive=True)
data = buf.getvalue()
print(f"dist.tar.gz: {len(data)} bytes ({len(data)/1024:.0f} KiB)")

# 2. sftp upload
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(host, port=port, username=user, password=pwd, timeout=30)
sftp = cli.open_sftp()
with sftp.open("/data/dist.tar.gz", "wb") as f:
    f.write(data)
print("uploaded /data/dist.tar.gz")

# 3. extract on host
def run(cmd, label=None):
    if label: print(f"--- {label} ---")
    _in, out, err = cli.exec_command(cmd, timeout=60)
    o = out.read().decode("utf-8","replace").rstrip(); e = err.read().decode("utf-8","replace").rstrip()
    if o: print(o)
    if e: print("[stderr]", e)
    return out.channel.recv_exit_status()
run("rm -rf /data/dist/* && tar -xzf /data/dist.tar.gz -C /data/dist && ls /data/dist/assets/ && cat /data/dist/index.html | grep -o 'index-[A-Za-z0-9_-]*\\.js'", "extract + verify new asset")
sftp.close(); cli.close()
print("=== dist deployed ===")
