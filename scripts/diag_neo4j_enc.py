#!/usr/bin/env python3
"""Diagnose neo4j Chinese corruption: is mock_data.cypher file clean UTF-8? Are neo4j node names U+FFFD?"""
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

def run(cmd, label=None):
    if label: print(f"--- {label} ---")
    _in, out, err = cli.exec_command(cmd, timeout=60)
    o = out.read().decode("utf-8","replace"); e = err.read().decode("utf-8","replace")
    print(o.rstrip())
    if e.strip(): print("[stderr]", e.rstrip())
    return out.channel.recv_exit_status()

# 1. cypher file: find a Chinese name, hex it
run("ls -la /data/deploy/mock_data.cypher /root/mock_data.cypher 2>/dev/null", "cypher files")
run("grep -m1 '远储能\\|北方储能\\|PROJECT_S' /data/deploy/mock_data.cypher 2>/dev/null | head -c 200", "sample cypher line (text)")
run("grep -m1 '远储能' /data/deploy/mock_data.cypher 2>/dev/null | head -c 80 | od -An -tx1", "hex of line with 远储能 (expect e8bf9c e582a8 e883bd)")
run("file /data/deploy/mock_data.cypher 2>/dev/null; locale 2>/dev/null | head -3", "file encoding + locale")

# 2. neo4j: query a node name + its hex
run("""docker exec metaprofile-readonly-neo4j-1 cypher-shell -u neo4j -p password --format plain "MATCH (n) WHERE n.name CONTAINS '储能' OR n.name STARTS WITH '远' RETURN n.name, labels(n) LIMIT 3;" 2>&1 | head -20""", "neo4j query name contains 储能")
run("""docker exec metaprofile-readonly-neo4j-1 cypher-shell -u neo4j -p password --format plain "MATCH (n:Tech) RETURN n.name LIMIT 3;" 2>&1 | head -10""", "neo4j Tech node names")
# hex of a neo4j name (pipe through od) - get one name
run("""docker exec metaprofile-readonly-neo4j-1 cypher-shell -u neo4j -p password --format plain "MATCH (n:Tech) RETURN n.name LIMIT 1;" 2>&1 | tail -1 | od -An -tx1 | head -3""", "hex of one neo4j Tech name")

cli.close()
print("=== diag done ===")
