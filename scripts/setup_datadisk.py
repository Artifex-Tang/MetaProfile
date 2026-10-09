#!/usr/bin/env python3
"""Mount vdb at /data, migrate docker data-root to /data/docker (matches old host).
Destructive on /dev/vdb only (fresh empty disk). Merges daemon.json keeping mirrors."""
import sys, json, paramiko
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
cli.connect(host, port=port, username=user, password=pwd, timeout=20)

def run(cmd, label=None, check=True):
    if label: print(f"--- {label} ---")
    _in, out, err = cli.exec_command(cmd, timeout=120)
    o = out.read().decode("utf-8","replace").rstrip()
    e = err.read().decode("utf-8","replace").rstrip()
    rc = out.channel.recv_exit_status()
    if o: print(o)
    if e: print(f"[stderr] {e}")
    print(f"[rc={rc}]")
    if check and rc != 0:
        print(f"!! FAIL: {label or cmd}")
    return rc

# 1. mkfs + mount vdb (idempotent: skip if already ext4)
run("blkid -s TYPE -o value /dev/vdb 2>/dev/null || echo none", "vdb fs type?")
# only mkfs if not ext4
run("""FSTYPE=$(blkid -s TYPE -o value /dev/vdb 2>/dev/null || echo none)
if [ "$FSTYPE" != "ext4" ]; then mkfs.ext4 -F /dev/vdb; else echo 'already ext4, skip mkfs'; fi""",
    "mkfs.ext4 vdb (conditional)")
run("mountpoint -q /data || mount /dev/vdb /data; mountpoint /data", "mount vdb /data")
run("mkdir -p /data/docker /data/dist /data/deploy", "mkdir data subdirs")

# 2. fstab persist (by UUID, idempotent)
run("""UUID=$(blkid -s UUID -o value /dev/vdb)
grep -q "$UUID" /etc/fstab || echo "UUID=$UUID /data ext4 defaults,noatime 0 2" >> /etc/fstab
grep "$UUID" /etc/fstab""", "fstab entry")

# 3. merge daemon.json: keep registry-mirrors, add data-root
print("--- merge daemon.json (add data-root) ---")
_in, out, err = cli.exec_command("cat /etc/docker/daemon.json", timeout=15)
cur = out.read().decode("utf-8","replace")
cfg = json.loads(cur)
cfg["data-root"] = "/data/docker"
newjson = json.dumps(cfg, indent=4, ensure_ascii=False)
# write back via sftp
sftp = cli.open_sftp()
with sftp.open("/etc/docker/daemon.json", "w") as f:
    f.write(newjson)
sftp.close()
print("daemon.json written:")
print(newjson)

# 4. restart docker, verify data-root
run("systemctl restart docker && sleep 3 && docker info 2>/dev/null | grep -E 'Docker Root|Storage' ", "restart docker + verify data-root")
run("df -h /data /", "disk after")
run("docker ps 2>&1 | head -2", "docker alive")
cli.close()
print("=== data disk setup done ===")
