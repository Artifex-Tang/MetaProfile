#!/usr/bin/env python3
"""Patch host deploy.sh copies (/root + /data/deploy) to add JAVA_TOOL_OPTIONS to cypher load."""
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

# sed: insert -e JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 after 'exec -T' on the cypher-load line
sed = r"""sed -i 's|exec -T neo4j cypher-shell|exec -T -e JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 neo4j cypher-shell|'"""
def run(cmd, label):
    print(f"--- {label} ---")
    _in, out, err = cli.exec_command(cmd, timeout=30)
    o = out.read().decode("utf-8","replace"); e = err.read().decode("utf-8","replace")
    print(o.rstrip())
    if e.strip(): print("[stderr]", e.rstrip()[:300])
    return out.channel.recv_exit_status()
for f in ["/root/deploy.sh", "/data/deploy/deploy.sh"]:
    run(f"test -f {f} && {sed} {f} && grep -n 'JAVA_TOOL_OPTIONS' {f} || echo '{f} not found'", f)
cli.close()
print("=== host deploy.sh patched ===")
