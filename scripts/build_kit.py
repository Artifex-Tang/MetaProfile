"""打包独立部署 kit(metaprofile-deploy-kit.tar.gz)。

产物结构(带顶层目录 metaprofile-deploy-kit/,解开后 cd 进去跑 deploy.sh;
旧版 kit 是文件平铺,解到 /root 一地鸡毛,这里修掉):

    metaprofile-deploy-kit/
      mp-all-images.tar.gz          5 个镜像(backend/frontend/postgres/neo4j/redis)
      certbot-image.tar.gz          certbot 镜像（仅 --with-certbot 时）
      dist.tar.gz                   前端构建产物
      docker-compose.readonly.yml
      nginx/{default.conf,locations.inc,default.https.conf.template}
      mock_data.sql / mock_data.cypher
      deploy.sh / enable_https.sh / .env.example
      部署指南.md（一步步操作）/ MANUAL.md（技术细节）

用法(项目根目录):
    python scripts/build_kit.py                 # 全量:构镜像 + 构前端 + 打包
    python scripts/build_kit.py --skip-build    # 复用已有镜像与 dist,只重打包(快)
    python scripts/build_kit.py --with-certbot  # 额外打 certbot 镜像(HTTPS 离线签发)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

# Windows 控制台默认 GBK，输出 ✅/→ 这类字符会 UnicodeEncodeError 打断脚本
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
KIT_NAME = "metaprofile-deploy-kit"
OUT_TARBALL = ROOT / f"{KIT_NAME}.tar.gz"
STAGE = ROOT / "build" / KIT_NAME

IMAGES = [
    "metaprofile-backend:latest",
    "metaprofile-frontend:latest",
    "postgres:15",
    "neo4j:5.16",
    "redis:7-alpine",
]

# (源, kit 内相对路径)
PLAIN_FILES = [
    (ROOT / "deploy" / "docker-compose.readonly.yml", "docker-compose.readonly.yml"),
    (ROOT / "deploy" / "mock_data.sql", "mock_data.sql"),
    (ROOT / "deploy" / "mock_data.cypher", "mock_data.cypher"),
    (ROOT / "deploy" / "cloud" / "deploy.sh", "deploy.sh"),
    (ROOT / "deploy" / "cloud" / "enable_https.sh", "enable_https.sh"),
    (ROOT / "deploy" / "cloud" / ".env.example", ".env.example"),
    (ROOT / "deploy" / "cloud" / "MANUAL.md", "MANUAL.md"),
    (ROOT / "deploy" / "cloud" / "部署指南.md", "部署指南.md"),
    (ROOT / "scripts" / "gen_mcp_config.py", "gen_mcp_config.py"),
    (ROOT / "deploy" / "cloud" / "mcp_clients_combined.json", "mcp_clients_combined.json"),
    (ROOT / "deploy" / "cloud" / "mcp_clients.md", "mcp_clients.md"),
    (ROOT / "deploy" / "cloud" / "mcp_clients_README.md", "mcp_clients_README.md"),
    (ROOT / "deploy" / "cloud" / "nginx" / "default.conf", "nginx/default.conf"),
    (ROOT / "deploy" / "cloud" / "nginx" / "locations.inc", "nginx/locations.inc"),
    (
        ROOT / "deploy" / "cloud" / "nginx" / "default.https.conf.template",
        "nginx/default.https.conf.template",
    ),
]

EXECUTABLE_IN_KIT = {"deploy.sh", "enable_https.sh"}
CERTBOT_IMAGE = "certbot/certbot"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def build_images() -> None:
    print("=== [1/5] 构建镜像 ===")
    run(["docker", "build", "-t", "metaprofile-backend:latest", "."], cwd=ROOT)
    run(
        ["docker", "build", "-t", "metaprofile-frontend:latest", "."],
        cwd=ROOT / "frontend",
    )
    for image in IMAGES[2:]:
        run(["docker", "pull", image])


def build_frontend_dist() -> None:
    print("=== [2/5] 构建前端 dist ===")
    run(["npm", "run", "build"], cwd=ROOT / "frontend")


def _save(images: list[str], target: Path) -> None:
    with target.open("wb") as fh:
        save = subprocess.Popen(["docker", "save", *images], stdout=subprocess.PIPE)
        # docker 镜像层本身已是压缩过的 blob，gzip 级别几乎不影响体积
        # （-1 与 -9 实测只差 0.4 MB），所以用 -1 省构建时间。
        # 真要缩包得从镜像本身下手 —— 加 .dockerignore 后 backend 镜像
        # 已从 2.55G 降到 999M（原来 COPY . . 把整个仓库连同上次的 kit 一起打进去了）。
        gzip_proc = subprocess.Popen(["gzip", "-1"], stdin=save.stdout, stdout=fh)
        assert save.stdout is not None
        save.stdout.close()
        if gzip_proc.wait() != 0 or save.wait() != 0:
            raise RuntimeError(f"docker save | gzip 失败: {images}")
    print(f"  → {target.name} {target.stat().st_size / 1e9:.2f} GB")


def save_images(stage: Path, with_certbot: bool) -> None:
    print("=== [3/5] 导出镜像(耗时最长,约 5-10 min) ===")
    _save(IMAGES, stage / "mp-all-images.tar.gz")

    if not with_certbot:
        print("  (跳过 certbot 镜像；HTTPS 时会现拉，加 --with-certbot 可离线)")
        return
    # 单独打包：只有要上 HTTPS 的部署才需要，避免所有人都背这 ~120MB
    print("  导出 certbot 镜像(HTTPS 离线签发用)…")
    run(["docker", "pull", CERTBOT_IMAGE])
    _save([CERTBOT_IMAGE], stage / "certbot-image.tar.gz")


def pack_dist(stage: Path) -> None:
    print("=== [4/5] 打包 dist + 配置文件 ===")
    dist_dir = ROOT / "frontend" / "dist"
    if not dist_dir.is_dir():
        raise SystemExit(f"前端产物不存在: {dist_dir}(去掉 --skip-build 重跑)")
    with tarfile.open(stage / "dist.tar.gz", "w:gz") as tar:
        for item in sorted(dist_dir.iterdir()):
            tar.add(item, arcname=item.name)

    for src, rel in PLAIN_FILES:
        if not src.is_file():
            raise SystemExit(f"缺文件: {src}")
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  + {rel}")


def make_tarball(stage: Path) -> None:
    print("=== [5/5] 打 kit tarball ===")

    def _filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
        # Windows 上没有 unix 权限位,显式给 .sh 加可执行位,免得目标机 bash 报 Permission denied
        if Path(info.name).name in EXECUTABLE_IN_KIT:
            info.mode = 0o755
        return info

    if OUT_TARBALL.exists():
        OUT_TARBALL.unlink()
    with tarfile.open(OUT_TARBALL, "w:gz") as tar:
        tar.add(stage, arcname=KIT_NAME, filter=_filter)
    size_gb = OUT_TARBALL.stat().st_size / 1e9
    print(f"\n✅ {OUT_TARBALL.name}  {size_gb:.2f} GB")
    print("   上传: python scripts/upload_kit.py")
    print(f"   目标机: tar -xzf {OUT_TARBALL.name} && cd {KIT_NAME} && bash deploy.sh")


def regen_mock_data(count: int) -> None:
    """重新生成 deploy/mock_data.{sql,cypher}（--sql-only 不连库）。

    注意：生成器目前对集合字段的迭代序没锁死，同参数重跑会产生等价但行序不同的
    文件。默认不重生成，避免在 kit 构建时引入无意义 diff。
    """
    print(f"=== 重新生成 mock 数据（每类 {count} 个实体）===")
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "gen_mock_data.py"),
            "--sql-only",
            "--count",
            str(count),
        ],
        cwd=ROOT,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="复用已有镜像与 frontend/dist，只重新打包",
    )
    parser.add_argument(
        "--with-certbot",
        action="store_true",
        help="额外打包 certbot 镜像（~120MB），让 HTTPS 签发也能离线进行",
    )
    parser.add_argument(
        "--regen-mock",
        type=int,
        metavar="COUNT",
        help="打包前重新生成 mock 数据，COUNT 为每类实体数量（如 --regen-mock 37）",
    )
    args = parser.parse_args()

    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    if args.regen_mock:
        regen_mock_data(args.regen_mock)

    if not args.skip_build:
        build_images()
        build_frontend_dist()
    else:
        print("=== 跳过构建（--skip-build），复用现有镜像与 dist ===")

    save_images(STAGE, with_certbot=args.with_certbot)
    pack_dist(STAGE)
    make_tarball(STAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
