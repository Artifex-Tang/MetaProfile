"""生成 7 个 MCP 工具的客户端配置，直接贴给使用方。

用法:
    python scripts/gen_mcp_config.py --base-url http://IP --token mp_xxx
    python scripts/gen_mcp_config.py --base-url https://域名 --token mp_xxx --combined
    python scripts/gen_mcp_config.py --base-url http://IP --gen-token
    python scripts/gen_mcp_config.py --base-url http://IP --token mp_xxx --output cfg.json
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from metaprofile.mcp_server.config_export import (  # noqa: E402
    render_all,
    render_combined,
    render_reference,
)

TOKEN_PREFIX = "mp_"


def generate_token() -> str:
    return TOKEN_PREFIX + secrets.token_hex(32)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        required=True,
        help="对外访问地址，如 http://47.120.41.179 或 https://mp.example.com",
    )
    parser.add_argument("--token", help="MCP_AUTH_TOKEN 的值；不传则配置里不含 headers")
    parser.add_argument(
        "--gen-token", action="store_true", help="生成一个随机 token 并使用它"
    )
    parser.add_argument(
        "--combined",
        action="store_true",
        help="输出一份合并配置（一次挂全部 7 个），而不是 7 段独立配置",
    )
    parser.add_argument(
        "--format",
        choices=("reference", "indented"),
        default="reference",
        help="分段配置的排版：reference=参考格式([]包裹+零缩进，默认)；indented=2 空格缩进",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="写入文件而非打印到屏幕（同目录另写一份 .token 记录所用 token）",
    )
    args = parser.parse_args()

    token = args.token
    if args.gen_token:
        token = generate_token()

    if args.combined:
        text = render_combined(args.base_url, token)
    elif args.format == "indented":
        text = render_all(args.base_url, token)
    else:
        text = render_reference(args.base_url, token)

    if args.output:
        args.output.write_text(text, encoding="utf-8")
        # --combined 产出的是单个 JSON；非合并是多段带标题文本，加 .md 后缀更合适
        print(f"已写入 {args.output}（{args.output.stat().st_size} 字节）")
        if token:
            tok = args.output.with_suffix(args.output.suffix + ".token")
            tok.write_text(f"MCP_AUTH_TOKEN={token}\n", encoding="utf-8")
            print(f"token 记录在 {tok}")
        if args.gen_token:
            print(
                f"\n⚠️ 务必把 MCP_AUTH_TOKEN={token} 写进部署机 .env"
                " 并重启 backend，否则 token 不生效。"
            )
    else:
        if args.gen_token:
            print("# 生成的 token（写进部署机的 .env：MCP_AUTH_TOKEN=<该值>，再重启 backend）")
            print(f"MCP_AUTH_TOKEN={token}\n")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
