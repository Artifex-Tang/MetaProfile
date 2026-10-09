#!/usr/bin/env python3
"""Test: does `docker compose exec -T -e JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 neo4j cypher-shell`
read UTF-8 stdin correctly? Write+read a Chinese string."""
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
    if e.strip(): print("[stderr]", e.rstrip()[:400])
    return out.channel.recv_exit_status()

CMP = "docker compose -f /data/deploy/docker-compose.readonly.yml"
# Test A: no JAVA_TOOL_OPTIONS (baseline - should be ?)
run(f"""echo "RETURN '远储能集团' AS x;" | {CMP} exec -T neo4j cypher-shell -u neo4j -p password --format plain 2>&1 | tail -5""", "A: baseline (no UTF-8 opt) — expect ???")
# Test B: with JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8
run(f"""echo "RETURN '远储能集团' AS x;" | {CMP} exec -T -e JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 neo4j cypher-shell -u neo4j -p password --format plain 2>&1 | tail -5""", "B: with file.encoding=UTF-8 — expect 远储能集团")
# Test C: with LANG=C.UTF-8 too
run(f"""echo "RETURN '远储能集团' AS x;" | {CMP} exec -T -e LANG=C.UTF-8 -e JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 neo4j cypher-shell -u neo4j -p password --format plain 2>&1 | tail -5""", "C: LANG+JVM opts — expect 远储能集团")

cli.close()
