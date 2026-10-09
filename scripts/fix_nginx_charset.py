#!/usr/bin/env python3
"""Add charset utf-8 to nginx.conf on host (bind-mounted /data/nginx.conf) + reload.
Fixes JS/CSS/JSON served without charset → CN-locale browser decodes as GBK → ??? in graphs."""
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
sftp = cli.open_sftp()

# 1. read current
with sftp.open("/data/nginx.conf", "r") as f:
    conf = f.read().decode("utf-8")

if "charset utf-8" in conf:
    print("charset already present, skip")
else:
    # insert after 'index index.html;' line
    inject = "\n    charset utf-8;\n    charset_types text/css text/plain text/xml application/javascript application/json image/svg+xml;"
    marker = "    index index.html;"
    if marker not in conf:
        print("!! marker 'index index.html;' not found; aborting"); sys.exit(1)
    conf = conf.replace(marker, marker + inject, 1)
    with sftp.open("/data/nginx.conf", "w") as f:
        f.write(conf)
    print("injected charset directives")

# 2. reload nginx (frontend container)
def run(cmd, label=None):
    if label: print(f"--- {label} ---")
    _in, out, err = cli.exec_command(cmd, timeout=30)
    o = out.read().decode("utf-8","replace").rstrip(); e = err.read().decode("utf-8","replace").rstrip()
    if o: print(o)
    if e: print("[stderr]", e)
    return out.channel.recv_exit_status()
run("docker exec metaprofile-readonly-frontend-1 nginx -t 2>&1 && docker exec metaprofile-readonly-frontend-1 nginx -s reload 2>&1", "nginx test + reload")
sftp.close(); cli.close()
print("=== charset fix applied ===")
