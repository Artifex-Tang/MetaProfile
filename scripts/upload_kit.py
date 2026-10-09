#!/usr/bin/env python3
"""Resumable SFTP upload of deploy kit to /root on host.
Checks remote partial size, appends from there. Safe to re-run."""
import sys, os, time, paramiko
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

env = {}
for line in Path("deploy/cloud/.env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
host = env["SSH_HOST"]; port = int(env.get("SSH_PORT", "22"))
user = env["SSH_USER"]; pwd = env["SSH_PASSWORD"]

LOCAL = "metaprofile-deploy-kit.tar.gz"
REMOTE = "/root/metaprofile-deploy-kit.tar.gz"
CHUNK = 1024 * 1024  # 1 MiB

total = os.path.getsize(LOCAL)
print(f"local size: {total} bytes ({total/1024/1024:.1f} MiB)")

cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(host, port=port, username=user, password=pwd, timeout=30, banner_timeout=30)
sftp = cli.open_sftp()

# resume: remote size
offset = 0
try:
    st = sftp.stat(REMOTE)
    offset = st.st_size
    print(f"remote partial: {offset} bytes — resuming")
except FileNotFoundError:
    print("remote: none — fresh upload")

if offset >= total:
    print("ALREADY COMPLETE")
else:
    mode = "ab" if offset > 0 else "wb"
    with open(LOCAL, "rb") as fin, sftp.open(REMOTE, mode) as fout:
        fin.seek(offset)
        sent = offset
        t0 = time.time()
        last = t0
        while True:
            buf = fin.read(CHUNK)
            if not buf:
                break
            fout.write(buf)
            sent += len(buf)
            now = time.time()
            if now - last >= 10:
                pct = sent / total * 100
                speed = (sent - offset) / (now - t0) / 1024
                print(f"  {sent/1024/1024:.1f}/{total/1024/1024:.1f} MiB  {pct:.1f}%  {speed:.0f} KiB/s")
                last = now
                sys.stdout.flush()
    print(f"upload done: {sent} bytes")

# verify size
st = sftp.stat(REMOTE)
print(f"remote final size: {st.st_size}  (match: {st.st_size == total})")
sftp.close(); cli.close()
print("=== upload done ===")
