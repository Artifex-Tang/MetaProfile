#!/usr/bin/env python3
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
def run(cmd):
    _in, out, err = cli.exec_command(cmd, timeout=120)
    o = out.read().decode("utf-8","replace"); e = err.read().decode("utf-8","replace")
    print(o)
    if e: print("[stderr]", e)
    return out.channel.recv_exit_status()
run("cd /root && tar -tzf metaprofile-deploy-kit.tar.gz | head -20")
run("cd /root && ls -la")
cli.close()
