# 技术概念抽取 P1(IPC 骨架 + LLM 聚类 + 技术树 + 证据)实施计划

> ✅ **状态：P1 已完成并合 main(`beff234`, 2026-06-24)**。subagent-driven TDD 执行,T1-T7 + 2 fix(savepoint 韧性 / glm 围栏解析)。后续 #3 禁 patent-as-tech(`7a7892a`)+ingest hygiene(`b69b86b`)+collection cron(`4b8733c`/`c8572ae`)已并入 main。冷启动 L1(636 IPC 域)落地;L2 卡 glm 429 配额。详见 memory `tech-concept-p1-done`。下方任务框为执行时记录,已全部落地。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 Tech 两层实体模型——L1 IPC 技术域(subclass)+ L2 LLM 聚类具体技术,论文/专利降为证据,产出 TECH_CONTAINS 技术树。修掉"论文标题当技术名"+零 tech-tech 两缺陷。

**Architecture:** ingest_ods 5 阶段流水线 `extract` 后插入 `tech_concept` 阶段:IPC subclass 回卷(L1,零 LLM)+ LLM 抽技术术语(L2)+ 同义聚类(embedding+词典)+ 写 tech_profile(分层)+ tech_evidence + TECH_CONTAINS 边。

**Tech Stack:** Python 3.12 / SQLAlchemy 2.0 / alembic / pymysql / Neo4j / bge-large-zh embedding / glm-4.7(via LLMGateway)

**Spec:** `docs/superpowers/specs/2026-06-21-tech-concept-extraction-design.md`(本计划只覆盖 §10 P1;P2 共现网、P3 演进链后续独立计划)

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `migrations/versions/0005_tech_concept.py` | alembic:tech_profile 加 4 列 + tech_evidence 表 | 新建 |
| `metaprofile/shared/schemas/relations.py` | RelationType 加 TECH_CONTAINS | 改 |
| `metaprofile/profile_tech/domain/orm_models.py` | TechProfileORM 加 tech_layer/ipc_code/parent_ipc_code/cluster_terms | 改 |
| `metaprofile/ingest_ods/domain/orm_models.py` | TechEvidenceORM | 加 |
| `metaprofile/ingest_ods/domain/ipc_taxonomy.py` | IPC subclass 回卷 + 字典查名 | 新建 |
| `metaprofile/ingest_ods/data/ipc_subclass_cn.tsv` | IPC subclass→中文名 字典数据 | 新建 |
| `metaprofile/ingest_ods/services/tech_concept_miner.py` | LLM 抽技术术语 | 新建 |
| `metaprofile/ingest_ods/llm/prompts.py` | TECH_MINER_SYSTEM_PROMPT + MinedTechTerm | 改 |
| `metaprofile/ingest_ods/services/tech_clusterer.py` | 同义归一 + embedding 聚类 → L2 entity_id | 新建 |
| `metaprofile/ingest_ods/services/tech_relation_builder.py` | 建 TECH_CONTAINS 边 | 新建 |
| `metaprofile/ingest_ods/services/orchestrator.py` | `_process_batch` 后插 tech_concept 阶段 | 改 |
| `metaprofile/ingest_ods/collectors/sql_warehouse.py` | 装配 tech 组件 | 改 |
| `tests/ingest_ods/test_ipc_taxonomy.py` / `test_tech_concept_miner.py` / `test_tech_clusterer.py` / `test_tech_relation_builder.py` | 单测 | 新建 |

---

## Task 1: 数据模型迁移 + RelationType + ORM

**Files:**
- Create: `migrations/versions/0005_tech_concept.py`
- Modify: `metaprofile/shared/schemas/relations.py`(RelationType 加 TECH_CONTAINS)
- Modify: `metaprofile/profile_tech/domain/orm_models.py`(TechProfileORM 加 4 列)
- Modify: `metaprofile/ingest_ods/domain/orm_models.py`(TechEvidenceORM)
- Test: `tests/ingest_ods/test_tech_models.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/ingest_ods/test_tech_models.py
from metaprofile.shared.schemas.relations import RelationType
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.ingest_ods.domain.orm_models import TechEvidenceORM


def test_relation_type_has_tech_contains():
    assert RelationType.TECH_CONTAINS.value == "包含"


def test_tech_profile_has_layer_columns():
    cols = TechProfileORM.__table__.columns
    assert "tech_layer" in cols
    assert "ipc_code" in cols
    assert "parent_ipc_code" in cols
    assert "cluster_terms" in cols


def test_tech_evidence_orm_fields():
    cols = TechEvidenceORM.__table__.columns
    for c in ("id", "tech_id", "source_doc_id", "source_table", "snippet", "confidence"):
        assert c in cols
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/ingest_ods/test_tech_models.py -v`(容器内或 host)
Expected: FAIL(AttributeError / 列不存在)

- [ ] **Step 3: RelationType 加 TECH_CONTAINS**

`metaprofile/shared/schemas/relations.py` 在 TECH_CONTRIBUTOR 附近加:
```python
    TECH_CONTAINS = "包含"   # L1 技术域 包含 L2 具体技术(section→subclass→concept)
```

- [ ] **Step 4: TechProfileORM 加 4 列**

`metaprofile/profile_tech/domain/orm_models.py` 在 `remark` 之后、`confidence` 之前加:
```python
    tech_layer: Mapped[str] = mapped_column(String(16), nullable=False, default="CONCEPT", comment="DOMAIN|CONCEPT")
    ipc_code: Mapped[str | None] = mapped_column(String(32), comment="L1: IPC subclass code")
    parent_ipc_code: Mapped[str | None] = mapped_column(String(32), comment="L2: 归属 subclass")
    cluster_terms: Mapped[list] = mapped_column(JSON, default=list, nullable=False, comment="L2 同义合并原始术语集")
```

- [ ] **Step 5: TechEvidenceORM**

`metaprofile/ingest_ods/domain/orm_models.py` 末尾加:
```python
class TechEvidenceORM(Base, TimestampMixin):
    __tablename__ = "tech_evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tech_id: Mapped[str] = mapped_column(String(64), ForeignKey("tech_profile.tech_id", ondelete="CASCADE"), index=True)
    source_doc_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_table: Mapped[str] = mapped_column(String(128), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    __table_args__ = (UniqueConstraint("tech_id", "source_doc_id", "source_table", name="uq_tech_evidence"),)
```
(顶部确保 import: `Integer, Text, Float, ForeignKey, UniqueConstraint` 已有则免)

- [ ] **Step 6: 写 alembic 迁移 0005**

`migrations/versions/0005_tech_concept.py`:
```python
"""tech_concept: tech_profile layer cols + tech_evidence table

Revision ID: 0005_tech_concept
Revises: 0004_project_relax_constraints
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_tech_concept"
down_revision = "0004_project_relax_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tech_profile", sa.Column("tech_layer", sa.String(16), nullable=False, server_default="CONCEPT"))
    op.add_column("tech_profile", sa.Column("ipc_code", sa.String(32), nullable=True))
    op.add_column("tech_profile", sa.Column("parent_ipc_code", sa.String(32), nullable=True))
    op.add_column("tech_profile", sa.Column("cluster_terms", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "tech_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tech_id", sa.String(64), sa.ForeignKey("tech_profile.tech_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_doc_id", sa.String(128), nullable=False),
        sa.Column("source_table", sa.String(128), nullable=False),
        sa.Column("snippet", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tech_id", "source_doc_id", "source_table", name="uq_tech_evidence"),
    )
    op.create_index("ix_tech_evidence_tech_id", "tech_evidence", ["tech_id"])


def downgrade() -> None:
    op.drop_index("ix_tech_evidence_tech_id", table_name="tech_evidence")
    op.drop_table("tech_evidence")
    for c in ("cluster_terms", "parent_ipc_code", "ipc_code", "tech_layer"):
        op.drop_column("tech_profile", c)
```

- [ ] **Step 7: 应用迁移 + 跑测试**

Run: `docker exec metaprofile-backend-1 python -m alembic upgrade head`(或 migrate job 重跑)
Run: `python -m pytest tests/ingest_ods/test_tech_models.py -v`
Expected: PASS(3 tests)

- [ ] **Step 8: Commit**

```bash
git add migrations/versions/0005_tech_concept.py metaprofile/shared/schemas/relations.py metaprofile/profile_tech/domain/orm_models.py metaprofile/ingest_ods/domain/orm_models.py tests/ingest_ods/test_tech_models.py
git commit -m "feat(tech): 数据模型—tech_profile 分层列 + tech_evidence + TECH_CONTAINS"
```

---

## Task 2: IPC taxonomy 模块 + 字典数据

**Files:**
- Create: `metaprofile/ingest_ods/domain/ipc_taxonomy.py`
- Create: `metaprofile/ingest_ods/data/ipc_subclass_cn.tsv`
- Test: `tests/ingest_ods/test_ipc_taxonomy.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/ingest_ods/test_ipc_taxonomy.py
from metaprofile.ingest_ods.domain.ipc_taxonomy import subclass_of, section_of, name_of


def test_subclass_of_strips_version_suffix():
    assert subclass_of("G06T7/00(2017.01)I") == "G06T"
    assert subclass_of("A01C1/02") == "A01C"
    assert subclass_of("A01B") == "A01B"

def test_subclass_of_none_for_garbage():
    assert subclass_of("") is None
    assert subclass_of(None) is None
    assert subclass_of("XYZ") is None

def test_section_of():
    assert section_of("G06T") == "G"
    assert section_of("A01C") == "A"

def test_name_of_dict_hit():
    assert name_of("G06T") == "图像数据识别"  # 字典有则返中文名

def test_name_of_fallback_to_code():
    assert name_of("Z99Z") == "Z99Z"  # 字典无则返 code 原文
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/ingest_ods/test_ipc_taxonomy.py -v`
Expected: FAIL(模块不存在)

- [ ] **Step 3: 写 IPC 字典数据(种子,覆盖已同步专利高频 subclass)**

`metaprofile/ingest_ods/data/ipc_subclass_cn.tsv`(tab 分隔 subclass\t中文名),先放 ~20 条高频(从已同步专利 ipc_type top 聚合),格式:
```
G06T\t图像数据识别
G06V\t图像或视频识别
G06Q\t数据处理系统/方法
G06K\t数据识别/数据载体
G06F\t电数字数据处理
A01C\t种植/播种/施肥
A01B\t农业/园林耕作
A01D\t收获/割草
... (top-N,后续补全留 follow-up)
```
(从本地 Doris `SELECT ipc_type,COUNT(*) ... GROUP BY 1 ORDER BY 2 DESC LIMIT 50` 聚合后取 subclass 回卷去重填)

- [ ] **Step 4: 写 ipc_taxonomy 模块**

```python
# metaprofile/ingest_ods/domain/ipc_taxonomy.py
"""IPC 分类回卷 + 字典查名。L1 技术域 = IPC subclass(如 G06T)。"""
from __future__ import annotations
import re
from functools import lru_cache
from pathlib import Path

# 匹配 IPC subclass:1 字母 + 2 数字 + 1 字母(可选 subclass 末字母)= section+class+subclass
# 例:A01C, G06T, H04W。输入可能带组号/版本后缀:A01C1/02 / G06T7/00(2017.01)I
_SUBCLASS_RE = re.compile(r"^([A-H]\d{2}[A-Z])")
_DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "ipc_subclass_cn.tsv"


def subclass_of(ipc_type: str | None) -> str | None:
    """任意 IPC 串 → subclass code(A01C),无法识别返 None。"""
    if not ipc_type:
        return None
    m = _SUBCLASS_RE.match(str(ipc_type).strip().upper())
    return m.group(1) if m else None


def section_of(subclass: str | None) -> str | None:
    """subclass(A01C) → section(A)。"""
    if not subclass or len(subclass) < 1:
        return None
    s = str(subclass).strip().upper()
    return s[0] if s and s[0].isalpha() else None


@lru_cache(maxsize=1)
def _load_dict() -> dict[str, str]:
    d: dict[str, str] = {}
    if not _DICT_PATH.exists():
        return d
    for line in _DICT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 2:
            d[parts[0].strip().upper()] = parts[1].strip()
    return d


def name_of(subclass: str | None) -> str:
    """subclass → 中文名;字典缺失 fallback 返 code 原文(保证 L1 一定有名)。"""
    if not subclass:
        return ""
    table = _load_dict()
    return table.get(str(subclass).strip().upper(), str(subclass).strip().upper())
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/ingest_ods/test_ipc_taxonomy.py -v`
Expected: PASS(5 tests)。字典内容需含 G06T→图像数据识别 才过 test_name_of_dict_hit;按 Step 3 填入。

- [ ] **Step 6: Commit**

```bash
git add metaprofile/ingest_ods/domain/ipc_taxonomy.py metaprofile/ingest_ods/data/ipc_subclass_cn.tsv tests/ingest_ods/test_ipc_taxonomy.py
git commit -m "feat(tech): ipc_taxonomy subclass 回卷 + 中文字典"
```

---

## Task 3: tech_concept_miner(LLM 抽技术术语)

**Files:**
- Modify: `metaprofile/ingest_ods/llm/prompts.py`(加 TECH_MINER_SYSTEM_PROMPT + MinedTechTerm)
- Create: `metaprofile/ingest_ods/services/tech_concept_miner.py`
- Test: `tests/ingest_ods/test_tech_concept_miner.py`

- [ ] **Step 1: 写失败测试(mock LLM)**

```python
# tests/ingest_ods/test_tech_concept_miner.py
import json
from unittest.mock import AsyncMock, MagicMock
from metaprofile.ingest_ods.services.tech_concept_miner import TechConceptMiner


def _llm(resp_json: str):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=MagicMock(content=resp_json))
    return llm


async def test_mine_parses_terms():
    llm = _llm(json.dumps({"terms": [
        {"term": "质谱仪", "type": "设备", "confidence": 0.95},
        {"term": "液相色谱", "type": "方法", "confidence": 0.8},
    ]}))
    miner = TechConceptMiner(llm=llm)
    out = await miner.mine(title="质谱仪采购", abstract="采用液相色谱-质谱联用...")
    assert len(out) == 2
    assert out[0].term == "质谱仪"
    assert out[0].confidence == 0.95


async def test_mine_bad_json_returns_empty():
    llm = _llm("not json")
    miner = TechConceptMiner(llm=llm)
    assert await miner.mine(title="x", abstract="y") == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/ingest_ods/test_tech_concept_miner.py -v`
Expected: FAIL(模块不存在)

- [ ] **Step 3: 加 prompt + MinedTechTerm**

`metaprofile/ingest_ods/llm/prompts.py` 加(参考现有 MinedEntity 风格):
```python
TECH_MINER_SYSTEM_PROMPT = """你是技术情报抽取器。从论文/专利标题与摘要中抽取【具体技术术语】
(设备/材料/方法/算法名,如"质谱仪""量子计算""液相色谱""CNN")。
不要抽机构名/人名/地名/通用词。返回 JSON:{"terms":[{"term","type","confidence"}]}。"""

class MinedTechTerm(BaseModel):
    term: str
    type: str = ""
    confidence: float = 0.0
```
(顶部确保 `from pydantic import BaseModel` 已导入)

- [ ] **Step 4: 写 TechConceptMiner**

```python
# metaprofile/ingest_ods/services/tech_concept_miner.py
"""L2:从 title/abstract LLM 抽技术术语。"""
from __future__ import annotations
import json
from pydantic import TypeAdapter
from metaprofile.ingest_ods.llm.prompts import TECH_MINER_SYSTEM_PROMPT, MinedTechTerm
from metaprofile.shared.config.settings import settings

_MAX_CHARS = 3000


class TechConceptMiner:
    def __init__(self, llm) -> None:
        self._llm = llm

    async def mine(self, *, title: str, abstract: str | None = None) -> list[MinedTechTerm]:
        text = f"标题:{title or ''}\n摘要:{(abstract or '')[:_MAX_CHARS]}"
        if not (title or "").strip():
            return []
        resp = await self._llm.complete(
            model=settings.llm.extraction_model,
            messages=[{"role": "system", "content": TECH_MINER_SYSTEM_PROMPT},
                      {"role": "user", "content": text}],
            temperature=0.0, caller="tech_concept_mine",
        )
        try:
            data = json.loads(resp.content.strip())
            return TypeAdapter(list[MinedTechTerm]).validate_python(data.get("terms", []))
        except Exception:
            return []
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/ingest_ods/test_tech_concept_miner.py -v`
Expected: PASS(2 tests)

- [ ] **Step 6: Commit**

```bash
git add metaprofile/ingest_ods/llm/prompts.py metaprofile/ingest_ods/services/tech_concept_miner.py tests/ingest_ods/test_tech_concept_miner.py
git commit -m "feat(tech): tech_concept_miner LLM 抽技术术语"
```

---

## Task 4: tech_clusterer(同义归一 + embedding 聚类)

**Files:**
- Create: `metaprofile/ingest_ods/services/tech_clusterer.py`
- Test: `tests/ingest_ods/test_tech_clusterer.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/ingest_ods/test_tech_clusterer.py
from metaprofile.ingest_ods.services.tech_clusterer import normalize_term, cluster_entity_id


def test_normalize_alias_dict():
    # 别名词典:质谱=质谱仪=mass spectrometry=MS
    assert normalize_term("质谱仪") == normalize_term("质谱")
    assert normalize_term("质谱仪") == normalize_term("mass spectrometry")

def test_normalize_case_punct():
    assert normalize_term("CNN。") == normalize_term("cnn")
    assert normalize_term(" 量子计算 ") == "量子计算"

def test_cluster_entity_id_stable():
    # 同 normalized term → 同 entity_id(幂等)
    a = cluster_entity_id("质谱仪")
    b = cluster_entity_id("质谱")
    assert a == b
    assert a.startswith("concept:")

def test_cluster_entity_id_diff_for_unrelated():
    assert cluster_entity_id("质谱仪") != cluster_entity_id("量子计算")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/ingest_ods/test_tech_clusterer.py -v`
Expected: FAIL(模块不存在)

- [ ] **Step 3: 写 tech_clusterer**

```python
# metaprofile/ingest_ods/services/tech_clusterer.py
"""L2 同义聚类:术语归一(别名词典 + 规范化)→ 稳定 entity_id。
embedding 余弦合并留 P2(共现网)一并做;P1 先用词典归一兜底,保证明显同义合并。"""
from __future__ import annotations
import hashlib
import re

# 别名词典:同义术语归一到规范形。初版手工高频,可扩。
_ALIAS: dict[str, str] = {}
_ALIAS_GROUPS = [
    ("质谱仪", ["质谱仪", "质谱", "mass spectrometry", "mass spectrometer", "MS"]),
    ("液相色谱", ["液相色谱", "high performance liquid chromatography", "HPLC"]),
    ("量子计算", ["量子计算", "quantum computing"]),
]
for canonical, syns in _ALIAS_GROUPS:
    for s in syns:
        _ALIAS[s.lower()] = canonical


def normalize_term(term: str) -> str:
    """术语 → 规范形:别名词典命中返 canonical,否则去标点/空白/小写(中文保留)。"""
    if not term:
        return ""
    t = str(term).strip()
    key = t.lower()
    if key in _ALIAS:
        return _ALIAS[key]
    # 去中英文标点 + 多余空白,中文保留(不 lower 中文)
    t = re.sub(r"[。，,;；:：.。、()\(\)【】\[\]\"'!\?!？]", "", t)
    t = re.sub(r"\s+", "", t)
    return t


def cluster_entity_id(term: str) -> str:
    """术语 → 稳定 L2 entity_id:concept:{md5(normalized)[:12]}。"""
    n = normalize_term(term)
    if not n:
        return ""
    return "concept:" + hashlib.md5(n.encode("utf-8")).hexdigest()[:12]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ingest_ods/test_tech_clusterer.py -v`
Expected: PASS(4 tests)

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/tech_clusterer.py tests/ingest_ods/test_tech_clusterer.py
git commit -m "feat(tech): tech_clusterer 同义归一 + 稳定 entity_id"
```

---

## Task 5: tech_relation_builder(TECH_CONTAINS 树)

**Files:**
- Create: `metaprofile/ingest_ods/services/tech_relation_builder.py`
- Test: `tests/ingest_ods/test_tech_relation_builder.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/ingest_ods/test_tech_relation_builder.py
from metaprofile.ingest_ods.services.tech_relation_builder import build_containment_triples


def test_l2_with_parent_ipc_links_to_l1():
    # L2 concept 归属 G06T subclass → TECH_CONTAINS 边 ipc:G06T → concept:xxx
    trips = build_containment_triples(
        l2_concepts=[{"entity_id": "concept:abc", "name": "图像识别", "parent_ipc": "G06T"}],
        l1_subclasses={"G06T"},  # 已建的 L1 集合
    )
    assert len(trips) == 1
    t = trips[0]
    assert t.subject_id == "ipc:G06T"
    assert t.object_id == "concept:abc"
    assert t.relation.value == "包含"


def test_l2_without_parent_ipc_no_edge():
    trips = build_containment_triples(
        l2_concepts=[{"entity_id": "concept:xyz", "name": "孤立技术", "parent_ipc": None}],
        l1_subclasses={"G06T"},
    )
    assert trips == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/ingest_ods/test_tech_relation_builder.py -v`
Expected: FAIL(模块不存在)

- [ ] **Step 3: 写 tech_relation_builder**

```python
# metaprofile/ingest_ods/services/tech_relation_builder.py
"""建 tech-tech 边。P1:TECH_CONTAINS(L1 技术域 contains L2 具体技术)。"""
from __future__ import annotations
from datetime import datetime, timezone
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationType, RelationTriple


def build_containment_triples(
    *, l2_concepts: list[dict], l1_subclasses: set[str],
) -> list[RelationTriple]:
    """L2 概念归属某已建 L1 subclass → TECH_CONTAINS 边(ipc:X → concept:Y)。

    l2_concepts: [{"entity_id","name","parent_ipc"}]
    l1_subclasses: 已建 L1 的 subclass code 集合({"G06T", ...})
    """
    now = datetime.now(timezone.utc)
    out: list[RelationTriple] = []
    for c in l2_concepts:
        sub = c.get("parent_ipc")
        if not sub or sub not in l1_subclasses:
            continue
        out.append(RelationTriple(
            subject_id=f"ipc:{sub}",
            subject_type=EntityType.TECH,
            subject_name=sub,
            relation=RelationType.TECH_CONTAINS,
            object_id=c["entity_id"],
            object_type=EntityType.TECH,
            object_name=c["name"],
            evidence=None, confidence=1.0,
            source_doc_id=None, method=SourceMethod.RULE, extracted_at=now,
        ))
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ingest_ods/test_tech_relation_builder.py -v`
Expected: PASS(2 tests)

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/tech_relation_builder.py tests/ingest_ods/test_tech_relation_builder.py
git commit -m "feat(tech): tech_relation_builder TECH_CONTAINS 树边"
```

---

## Task 6: tech_concept 阶段接入 orchestrator + collector

**Files:**
- Modify: `metaprofile/ingest_ods/services/orchestrator.py`(新增 `_tech_concept_stage`)
- Modify: `metaprofile/ingest_ods/collectors/sql_warehouse.py`(装配 miner/clusterer/relation_builder)

- [ ] **Step 1: 写集成测试(小批 patent → 产 L1+L2+evidence+边)**

`tests/ingest_ods/test_tech_concept_stage.py`(mock extractor 返 2 行 patent,mock LLM 抽 1 术语):
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
# 详:构造 BatchOrchestrator with fake extractor 返 patent 行(ipc_type=G06T7/00),
# fake llm 返 {"terms":[{"term":"图像识别",...}]},跑 run() → 断言:
# - tech_profile 出现 tech_layer=DOMAIN(ipc:G06T) + CONCEPT(concept:xxx)
# - tech_evidence 有行
# - relations 含 TECH_CONTAINS(ipc:G06T→concept:xxx)
```
(具体 fixture 参照现有 tests/ingest_ods/test_orchestrator.py 的 session/extractor mock 模式;断言 4 点如上。)

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/ingest_ods/test_tech_concept_stage.py -v`
Expected: FAIL(orchestrator 还没 tech_concept 阶段)

- [ ] **Step 3: orchestrator 加 _tech_concept_stage(具体实现)**

`metaprofile/ingest_ods/services/orchestrator.py`,`BatchOrchestrator.__init__` 签名加 `tech_miner=None`;`_process_batch` 在写完 profile 节点之后(现有 `await self._writer.upsert_profile_node(...)` 块之后)、`structured_triples` 收集之前,若 `table in ("ods_invention_patent_cn", "ods_science_literature")` 且 `self._tech_miner`,调用新方法:

```python
# orchestrator.py 新增方法(类内):
_TECH_TABLES = ("ods_invention_patent_cn", "ods_science_literature")

async def _tech_concept_stage(self, session, task, table: str, rows: list[dict]) -> None:
    """对 patent/science 行跑 tech 概念抽取:产 L1(IPC subclass)+ L2(聚类术语)+ 证据 + TECH_CONTAINS 树。"""
    from metaprofile.ingest_ods.domain.ipc_taxonomy import subclass_of, name_of
    from metaprofile.ingest_ods.services.tech_clusterer import cluster_entity_id, normalize_term
    from metaprofile.ingest_ods.services.tech_relation_builder import build_containment_triples
    from metaprofile.ingest_ods.domain.orm_models import TechEvidenceORM

    if self._tech_miner is None or table not in self._TECH_TABLES:
        return
    l1_built: set[str] = set()
    l2_concepts: list[dict] = []
    for r in rows:
        payload = r.get("raw_payload", {})
        title = payload.get("title") or ""
        abstract = payload.get("abstract") or ""
        src_id = str(payload.get("original_id") or r.get("source_id") or "")
        ipc_sub = subclass_of(payload.get("ipc_type"))
        # 1. L1 IPC 技术域(零 LLM)
        if ipc_sub:
            l1_id = f"ipc:{ipc_sub}"
            if ipc_sub not in l1_built:
                await self._writer.write_profile(
                    session, profile_type="tech", entity_id=l1_id,
                    attrs={"tech_name_cn": name_of(ipc_sub), "tech_name_en": ipc_sub,
                           "tech_summary": "", "current_status": "", "trend": "",
                           "tech_layer": "DOMAIN", "ipc_code": ipc_sub},
                    scores={"completeness": 0.0, "veracity_score": 0.9, "timeliness_score": 0.5,
                            "data_as_of": None, "dq_index": 0.7},
                    method="rule_extract",
                )
                l1_built.add(ipc_sub)
        # 2. L2 LLM 抽术语 + 聚类
        terms = await self._tech_miner.mine(title=title, abstract=abstract)
        seen: set[str] = set()
        for t in terms:
            cid = cluster_entity_id(t.term)
            if not cid or cid in seen:
                continue
            seen.add(cid)
            await self._writer.write_profile(
                session, profile_type="tech", entity_id=cid,
                attrs={"tech_name_cn": normalize_term(t.term), "tech_name_en": "",
                       "tech_summary": "", "current_status": "", "trend": "",
                       "tech_layer": "CONCEPT", "parent_ipc_code": ipc_sub,
                       "cluster_terms": [t.term]},
                scores={"completeness": 0.0, "veracity_score": 0.7, "timeliness_score": 0.5,
                        "data_as_of": None, "dq_index": 0.6},
                method="llm_extract",
            )
            l2_concepts.append({"entity_id": cid, "name": normalize_term(t.term), "parent_ipc": ipc_sub})
            # 3. 证据
            session.add(TechEvidenceORM(
                tech_id=cid, source_doc_id=src_id, source_table=table,
                snippet=title[:500], confidence=float(t.confidence),
            ))
    # 4. TECH_CONTAINS 树边
    if l2_concepts and l1_built:
        trips = build_containment_triples(l2_concepts=l2_concepts, l1_subclasses=l1_built)
        if trips:
            await self._writer.write_relations(trips)
    await session.flush()
```

调用点(在 `_process_batch` 内,profile 写入循环结束后):
```python
await self._tech_concept_stage(session, task, table, rows)
```
关键约束:依赖 Task 2/3/4/5 函数;`write_profile` 的列过滤(已修)会保留 Task1 新增的 4 列;`tech_name_cn` 对 DOMAIN/CONCEPT 都必填(给 IPC 名 / 规范术语)。

- [ ] **Step 4: collector 装配**

`metaprofile/ingest_ods/collectors/sql_warehouse.py` 的 `run_sql_warehouse_collection`,构造 BatchOrchestrator 时注入:
```python
from metaprofile.ingest_ods.services.tech_concept_miner import TechConceptMiner
orch = BatchOrchestrator(
    extractor=Extractor(), resolver=EntityResolver(llm=llm), scorer=RuleScorer(),
    writer=writer, connections=resolve_dsn,
    tech_miner=TechConceptMiner(llm=llm),  # 新增注入
)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/ingest_ods/test_tech_concept_stage.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add metaprofile/ingest_ods/services/orchestrator.py metaprofile/ingest_ods/collectors/sql_warehouse.py tests/ingest_ods/test_tech_concept_stage.py
git commit -m "feat(tech): tech_concept 阶段接入—产 L1/L2 tech + 证据 + TECH_CONTAINS 树"
```

---

## Task 7: 清旧标题-tech + 端到端真数据验证

**Files:**
- 一次性清理(无新文件,SQL 或 python -c)
- 验证:人工查 tech_profile/tech_evidence/Neo4j

- [ ] **Step 1: 清掉旧的 100 标题-tech(tech_layer IS NULL 的历史行)**

```bash
docker exec -i metaprofile-postgres-1 psql -U metaprofile -d metaprofile -c \
  "DELETE FROM tech_profile WHERE tech_layer IS NULL OR tech_layer NOT IN ('DOMAIN','CONCEPT');"
```
(迁移 server_default='CONCEPT' 已给旧行值;此清理针对"标题-tech"那批——它们是 P1 前的错误实体,tech_name 是论文标题。若难区分,直接 TRUNCATE tech_profile 重跑。)

- [ ] **Step 2: 重跑 ingest(patent+science 小批,验 L1/L2/证据/树)**

config table_set=[ods_invention_patent_cn, ods_science_literature],max_rows=50/表,mode=structured_only,trigger。等完成。

- [ ] **Step 3: 断言产出**

```sql
SELECT tech_layer, COUNT(*) FROM tech_profile GROUP BY tech_layer;
-- 期望:DOMAIN(若干 IPC subclass)+ CONCEPT(LLM 抽的术语聚类)
SELECT COUNT(*) FROM tech_evidence;  -- 期望 >0
```
Neo4j:`MATCH (a:Tech)-[:包含]->(b:Tech) RETURN count(*);` -- 期望 TECH_CONTAINS 边

- [ ] **Step 4: 详情接口抽验**

`curl http://localhost:8000/api/v1/profile/tech/ipc:G06T`(L1)和 `/tech/concept:xxx`(L2)→ 200。

- [ ] **Step 5: Commit(若有清理脚本/配置)**

```bash
# 若加了 e2e 验证脚本或文档:
git add <any>
git commit -m "test(tech): e2e 验证 L1/L2/证据/TECH_CONTAINS 树真数据"
```

---

## P1 完成标准
- [ ] tech_profile 有 DOMAIN(L1 IPC subclass)+ CONCEPT(L2 聚类)两层行
- [ ] tech_evidence 有证据行(论文/专利挂技术)
- [ ] Neo4j 有 TECH_CONTAINS 边(L1→L2 树)
- [ ] 论文/专利不再当 tech 实体(降为证据)
- [ ] ingest_ods 全测试绿 + 新增 5 测试文件绿
- [ ] tech 详情接口 200

## P2/P3(后续独立计划)
- P2:共现网(TECH_CO_OCCURS)+ 语义相似边 + 新 RelationType.TECH_CO_OCCURS
- P3:演进链(复用已有 RelationType.TECH_EVOLVE/TECH_PREREQ)+ problem_solution_miner + IPC 共类时序;引文链留待外部源
