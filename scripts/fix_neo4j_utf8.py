#!/usr/bin/env python3
"""Reload mock_data.cypher into neo4j with JVM file.encoding=UTF-8.
Root cause: cypher-shell JVM default charset != UTF-8 -> Chinese stored as '?'.
Fix: JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 forces UTF-8 stdin read.
mock_data.cypher self-cleans (DETACH DELETE) then recreates."""
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

def run(cmd, label=None, timeout=120):
    if label: print(f"--- {label} ---", flush=True)
    _in, out, err = cli.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8","replace"); e = err.read().decode("utf-8","replace")
    print(o.rstrip())
    if e.strip(): print("[stderr]", e.rstrip()[:500])
    return out.channel.recv_exit_status()

CYPHER = "/data/deploy/mock_data.cypher"
CMP = "docker compose -f /data/deploy/docker-compose.readonly.yml"
EXEC = f"{CMP} exec -T -e JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 neo4j cypher-shell -u neo4j -p password --format plain"

# 1. reload with UTF-8 JVM
run(f"cat {CYPHER} | {EXEC} 2>&1 | tail -6", "reload neo4j (UTF-8 JVM)", timeout=240)

# 2. verify neo4j node names clean Chinese
run(f'{EXEC} "MATCH (n:Tech) RETURN n.name LIMIT 3;" 2>&1 | grep -v JAVA_TOOL | head -6', "neo4j Tech names after reload")
run(f'{EXEC} "MATCH (n:Org) RETURN n.name LIMIT 3;" 2>&1 | grep -v JAVA_TOOL | head -6', "neo4j Org names after reload")

cli.close()
print("=== neo4j reload done ===")
