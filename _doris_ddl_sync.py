# -*- coding: utf-8 -*-
"""
DDL 同步脚本：从云 Doris 抽 39 表 DDL → 改单副本 → 写 _doris_local_schema.sql →
（可选 --apply）应用到本地 Doris FE。

用法：
  python _doris_ddl_sync.py             # 仅生成 SQL 文件
  python _doris_ddl_sync.py --apply     # 生成 + 应用到本地 Doris

云端=源(只读)，本地=目标。两库同方言(Doris 2.1)，故 DDL 零转换，只把副本数 3→1。
"""
import sys, re

# ── 云端(源，只读) ───────────────────────────────────────────
CLOUD = dict(host="10.242.0.1", port=9030, user="gz_kt5",
             password="92f5IRTld93lDPKYZZ5p", database="ods_zbzx",
             charset="utf8mb4", connect_timeout=15, read_timeout=120)

# ── 本地(目标) ───────────────────────────────────────────────
#   部署后改这里。默认 FE 容器映射 127.0.0.1:9030，root 无密码（手册里设）。
LOCAL = dict(host="127.0.0.1", port=9030, user="root",
             password="", database="ods_zbzx",
             charset="utf8mb4", connect_timeout=15, read_timeout=300)

OUT_SQL = "_doris_local_schema.sql"
DO_APPLY = "--apply" in sys.argv


def fetch_ddl():
    import pymysql
    c = pymysql.connect(**CLOUD)
    cur = c.cursor()
    cur.execute("SHOW TABLES")
    tables = [r[0] for r in cur.fetchall()]
    print(f"云端表数: {len(tables)}")
    blocks = []
    for t in tables:
        cur.execute(f"SHOW CREATE TABLE `{t}`")
        ddl = cur.fetchone()[1]
        # 单副本改写（本地 1 BE，3 副本建表会失败）。
        # 同时覆盖 replication_allocation 与 dynamic_partition.replication_allocation（保留前缀）。
        ddl = re.sub(r'((?:dynamic_partition\.)?replication_allocation)"\s*=\s*"tag\.location\.default:\s*\d+"',
                     r'\1" = "tag.location.default: 1"', ddl)
        # 兜底：若用 replication_num 属性
        ddl = re.sub(r'"replication_num"\s*=\s*"\d+"', '"replication_num" = "1"', ddl)
        blocks.append(f"DROP TABLE IF EXISTS `{t}`;\n{ddl};")
    c.close()
    return tables, blocks


def write_sql(tables, blocks):
    header = ("-- 自动生成：云端 ods_zbzx DDL（副本→1）。Doris 2.1。\n"
              "-- 由 _doris_ddl_sync.py 生成，勿手改；重跑覆盖。\n\n"
              "CREATE DATABASE IF NOT EXISTS `ods_zbzx`;\nUSE `ods_zbzx`;\n\n")
    body = "\n\n".join(blocks) + "\n"
    with open(OUT_SQL, "w", encoding="utf-8") as f:
        f.write(header + body)
    print(f"已写 {OUT_SQL}（{len(tables)} 表）")


def apply_local():
    import pymysql
    c = pymysql.connect(**LOCAL)
    cur = c.cursor()
    with open(OUT_SQL, "r", encoding="utf-8") as f:
        sql = f.read()
    # 按分号粗分语句（DDL 内无分号，安全）
    stmts = [s.strip() for s in sql.split(";\n") if s.strip() and not s.strip().startswith("--")]
    ok = 0
    for s in stmts:
        try:
            cur.execute(s)
            ok += 1
        except Exception as e:
            # 建库/USE/建表混合，容错打印
            print(f"  SKIP: {str(e)[:120]}")
    c.commit()
    c.close()
    print(f"本地应用语句 {ok}/{len(stmts)}")


if __name__ == "__main__":
    tables, blocks = fetch_ddl()
    write_sql(tables, blocks)
    if DO_APPLY:
        print("应用 DDL 到本地 Doris ...")
        apply_local()
    print("done.")
