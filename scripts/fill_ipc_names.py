"""LLM 批量补 IPC subclass 中文名(Phase D 收尾:636 域中 595 个裸码)。

读 tech_profile DOMAIN 层缺中文名的域 → glm 批量命名(WIPO IPC 标准语义)
→ 回写 tech_name_cn + 追加 ipc_subclass_cn.tsv。幂等(已有名跳过)。
"""
import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pydantic import Field
from sqlalchemy import select

from metaprofile.shared.config.settings import settings
from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.llm.function_calling import call_with_schema
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import ProfileBase


class IPCNameItem(ProfileBase):
    code: str
    name_cn: str


class IPCNameBatch(ProfileBase):
    names: list[IPCNameItem] = Field(default_factory=list)


SYSTEM = """你是 WIPO 国际专利分类(IPC)专家。给定 IPC subclass 码(如 G06V),
给出其中文标准领域名(简洁术语,≤10 字,如 G06V=图像数据处理)。只输出确定语义;
不确定的给最合理译名并保持术语风格统一。"""


async def main(batch_size: int = 100) -> None:
    gw = LLMGateway()
    async with get_session() as s:
        rows = (await s.execute(
            select(__import__("metaprofile.profile_tech.domain.orm_models",
                              fromlist=["TechProfileORM"]).TechProfileORM)
            .where(__import__("metaprofile.profile_tech.domain.orm_models",
                              fromlist=["TechProfileORM"]).TechProfileORM.tech_layer == "DOMAIN")
        )).scalars().all()
        todo = [t for t in rows
                if t.ipc_code and (not t.tech_name_cn or t.tech_name_cn == t.ipc_code)]
        print("todo", len(todo))
        for i in range(0, len(todo), batch_size):
            batch = todo[i:i + batch_size]
            codes = [t.ipc_code for t in batch]
            try:
                res, _ = await call_with_schema(
                    gateway=gw, model=settings.llm.agent_model,
                    system_prompt=SYSTEM,
                    user_prompt="codes: " + ", ".join(codes),
                    function_name="name_ipc_batch",
                    function_description="批量给出 IPC subclass 中文名",
                    output_schema=IPCNameBatch,
                    caller="scripts.fill_ipc_names",
                )
            except Exception as exc:  # noqa: BLE001
                print("batch failed", exc)
                continue
            got: dict = {}
            for x in res.names or []:
                code = getattr(x, "code", None) or (x.get("code") if isinstance(x, dict) else None)
                name = (getattr(x, "name_cn", None)
                        or (x.get("name_cn") if isinstance(x, dict) else None))
                if code and name:
                    got[str(code).strip().upper()] = str(name).strip()
            for t in batch:
                if t.ipc_code in got:
                    t.tech_name_cn = got[t.ipc_code]
            print(f"named {len(got)}/{len(batch)} in batch {i//batch_size}")
        await s.commit()

    # 追加 tsv
    tsv = __import__("pathlib").Path(
        "metaprofile/ingest_ods/data/ipc_subclass_cn.tsv")
    have = set()
    if tsv.exists():
        for line in tsv.read_text(encoding="utf-8").splitlines():
            if line.strip():
                have.add(line.split("\t")[0])
    add = 0
    with tsv.open("a", encoding="utf-8") as f:
        async with get_session() as s:
            rows = (await s.execute(
                select(__import__("metaprofile.profile_tech.domain.orm_models",
                                  fromlist=["TechProfileORM"]).TechProfileORM)
                .where(__import__("metaprofile.profile_tech.domain.orm_models",
                                  fromlist=["TechProfileORM"]).TechProfileORM.tech_layer == "DOMAIN")
            )).scalars().all()
            for t in rows:
                if t.ipc_code and t.tech_name_cn and t.ipc_code not in have \
                        and t.tech_name_cn != t.ipc_code:
                    f.write(f"{t.ipc_code}\t{t.tech_name_cn}\n")
                    add += 1
    print("tsv appended", add)


if __name__ == "__main__":
    asyncio.run(main())
