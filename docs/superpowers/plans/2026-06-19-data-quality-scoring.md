# 画像数据质量评分（规则型）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 ingest_ods 的 LLM Scorer 重写为确定性规则评分（completeness/veracity/timeliness + 复合 dq_index），对齐 ISO 25012 + DAMA，去掉评分阶段的 LLM 依赖。

**Architecture:** 新建 `quality_rules.py`（纯函数：时效衰减 / 来源可信 / 一致性 / 权威信号）；`scorer.py` 的 `Scorer` 改为 `RuleScorer`（无 llm 注入，接口签名不变 → orchestrator 几乎零改）；completeness 复用 `foundation/enrichment/completeness.score_completeness`；scorer 返回 dict 含 5 字段（completeness/veracity_score/timeliness_score/data_as_of/dq_index），writer 落库；migration 0005 加 `dq_index` 列；4 画像 response 暴露 `dq_index`。可调参数进 `StorageThresholds`。

**Tech Stack:** Python 3.12 / SQLAlchemy 2 async / pydantic / alembic / pytest-asyncio。无新依赖。

**Spec:** `docs/superpowers/specs/2026-06-19-data-quality-scoring-design.md`

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `metaprofile/shared/config/settings.py` | 评分可调参数（来源权重/半衰期/权重） | 改 StorageThresholds |
| `metaprofile/ingest_ods/services/quality_rules.py` | 纯函数评分算法 | 新建 |
| `metaprofile/ingest_ods/services/scorer.py` | RuleScorer（装配+返回 dict） | 重写 |
| `metaprofile/ingest_ods/services/orchestrator.py` | 注入 RuleScorer + 兜底 dict | 改 2 处 |
| `metaprofile/ingest_ods/services/writer.py` | 落 completeness + dq_index | 改 merged |
| `metaprofile/profile_{tech,org,person,project}/domain/orm_models.py` | dq_index 列 | 改 4 文件 |
| `migrations/versions/0005_dq_index.py` | dq_index 列 DDL | 新建 |
| `metaprofile/profile_{tech,org,person,project}/schemas/response.py` | 暴露 dq_index | 改 4 文件 |
| `tests/ingest_ods/test_quality_rules.py` + `test_scorer.py` | 单测 | 新建 |

---

## Task 1: settings 加评分参数

**Files:**
- Modify: `metaprofile/shared/config/settings.py:116` (class StorageThresholds)

- [ ] **Step 1: 读现有 StorageThresholds 确认字段**

Run: `grep -nA20 "class StorageThresholds" metaprofile/shared/config/settings.py`
确认含 `enrichment_auto_accept`/`enrichment_review_min`/`completeness_enrich_trigger` 等。

- [ ] **Step 2: 在 StorageThresholds 末尾追加评分参数**

在 `class StorageThresholds(BaseSettings):` 内最后一个字段后追加（注意缩进 4 空格）：

```python
    # ── 数据质量评分（规则型，ISO 25012 对齐；详见 quality_rules.py）──
    # 来源可信度基线（按数据进入通道）
    source_trust_ods: float = 0.90        # ODS Doris 官方库（sql_warehouse 抽取）
    source_trust_llm: float = 0.70        # LLM 补全（enrich）
    source_trust_import: float = 0.60     # 批量导入 JSON / 手工
    source_trust_ugc: float = 0.40        # UGC / 网页抓取
    source_trust_unknown: float = 0.50    # 缺来源信息兜底
    authority_bonus_each: float = 0.05    # 每个权威信号加分（DOI/引用/官方编号）
    authority_bonus_cap: float = 0.15     # 权威加分上限
    consistency_factor_ok: float = 1.0    # 跨字段一致
    consistency_factor_bad: float = 0.85  # 任一一致性检查失败
    timeliness_halflife_days: int = 180   # 时效指数衰减半衰期
    dq_weight_completeness: float = 0.4   # 复合 DQI 权重（Σ=1.0，可调）
    dq_weight_veracity: float = 0.3
    dq_weight_timeliness: float = 0.3
```

- [ ] **Step 3: 验证 import 不报错**

Run: `python -c "from metaprofile.shared.config.settings import settings; print(settings.thresholds.source_trust_ods, settings.thresholds.timeliness_halflife_days)"`
Expected: `0.9 180`

- [ ] **Step 4: Commit**

```bash
git add metaprofile/shared/config/settings.py
git commit -m "feat(scoring): StorageThresholds 加规则评分参数(来源权重/半衰期/DQI权重)"
```

---

## Task 2: quality_rules.py 纯函数 + 单测（TDD）

**Files:**
- Create: `metaprofile/ingest_ods/services/quality_rules.py`
- Test: `tests/ingest_ods/test_quality_rules.py`

- [ ] **Step 1: 先写失败测试**

Create `tests/ingest_ods/test_quality_rules.py`（若 `tests/ingest_ods/` 无 `__init__.py` 则建）：

```python
from datetime import date, timedelta
from metaprofile.ingest_ods.services.quality_rules import (
    timeliness_score, credibility_score, consistency_factor, authority_bonus,
)


def test_timeliness_fresh():
    assert timeliness_score(date.today()) == 1.0

def test_timeliness_halflife():
    # 半衰期 180 天 → ≈0.5
    s = timeliness_score(date.today() - timedelta(days=180))
    assert 0.49 <= s <= 0.51

def test_timeliness_none():
    assert timeliness_score(None) == 0.0

def test_timeliness_old():
    assert timeliness_score(date.today() - timedelta(days=3650)) < 0.01


def test_authority_bonus_cap():
    # 4 个信号 → cap 0.15
    attrs = {"doi": "10.1/x", "citation": "ref", "patent_no": "P1", "usc_code": "U1"}
    assert authority_bonus(attrs) == 0.15

def test_authority_bonus_none():
    assert authority_bonus({}) == 0.0


def test_consistency_ok():
    # tech: invention_date <= application_date
    assert consistency_factor("tech", {"invention_date": date(2020,1,1), "application_date": date(2021,1,1)}) == 1.0

def test_consistency_bad_dates():
    assert consistency_factor("tech", {"invention_date": date(2022,1,1), "application_date": date(2021,1,1)}) == 0.85

def test_consistency_missing_dates():
    # 无日期 → 不算失败
    assert consistency_factor("tech", {}) == 1.0


def test_credibility_ods_with_doi():
    src = {"source_table": "ods_science_literature"}
    attrs = {"doi": "10.1/x"}
    # 0.9 (ods) + 0.05 (doi) = 0.95, × 1.0
    assert abs(credibility_score(src, attrs) - 0.95) < 0.001

def test_credibility_cap_and_factor():
    src = {"source_table": "ods_x"}
    attrs = {"doi": "1", "citation": "2", "patent_no": "3",
             "invention_date": date(2022,1,1), "application_date": date(2021,1,1)}
    # (0.9 + 0.15) * 0.85 = 0.8925
    assert abs(credibility_score(src, attrs) - 0.8925) < 0.001
```

- [ ] **Step 2: 跑测试确认失败**

Run: `py -3.12 -m pytest tests/ingest_ods/test_quality_rules.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'metaprofile.ingest_ods.services.quality_rules'`）

- [ ] **Step 3: 实现 quality_rules.py**

Create `metaprofile/ingest_ods/services/quality_rules.py`：

```python
"""数据质量评分纯函数（规则型，ISO 25012 对齐）。零 LLM、确定性、可单测。

- timeliness: data_as_of 指数衰减（halflife 天半衰期）
- credibility(真实性=Credibility+Accuracy): 来源权重 + 权威信号 + 一致性乘子
- authority_bonus: DOI/引用/官方编号 信号加分（cap）
- consistency_factor: 跨字段一致性（日期顺序等）
"""
from __future__ import annotations

import math
from datetime import date

from metaprofile.shared.config.settings import settings

# 权威信号字段（存在即 +bonus）
_AUTHORITY_FIELDS = ("doi", "citation", "usc_code", "orcid", "patent_no", "project_no")
# 来源表前缀 → 通道
_UGC_HINTS = ("web", "crawl", "ugc")


def timeliness_score(data_as_of: date | None) -> float:
    """时效性：exp(-age_days / halflife)。无日期 → 0。"""
    if data_as_of is None:
        return 0.0
    age = (date.today() - data_as_of).days
    if age < 0:
        age = 0
    halflife = settings.thresholds.timeliness_halflife_days
    return max(0.0, min(1.0, math.exp(-age / halflife)))


def authority_bonus(attrs: dict) -> float:
    """权威信号加分：每个存在的 doi/citation/编号 +each，cap 上限。"""
    t = settings.thresholds
    n = sum(1 for f in _AUTHORITY_FIELDS if attrs.get(f) not in (None, "", []))
    return min(t.authority_bonus_cap, n * t.authority_bonus_each)


def consistency_factor(profile_type: str, attrs: dict) -> float:
    """跨字段一致性乘子。tech: invention_date<=application_date；失败→bad 因子。"""
    t = settings.thresholds
    inv = attrs.get("invention_date")
    app = attrs.get("application_date")
    if inv and app and isinstance(inv, date) and isinstance(app, date) and inv > app:
        return t.consistency_factor_bad
    # project: start_date <= end_date
    start = attrs.get("start_date"); end = attrs.get("end_date")
    if profile_type == "project" and start and end and isinstance(start, date) and isinstance(end, date) and start > end:
        return t.consistency_factor_bad
    return t.consistency_factor_ok


def _source_trust(src: dict) -> float:
    """来源可信度基线：按 source_table/通道。"""
    t = settings.thresholds
    tbl = (src.get("source_table") or "").lower()
    if tbl.startswith("ods_"):
        return t.source_trust_ods
    if any(h in tbl for h in _UGC_HINTS):
        return t.source_trust_ugc
    ch = (src.get("source_channel") or "").lower()
    if ch in ("llm", "enrich"):
        return t.source_trust_llm
    if ch in ("import", "bulk"):
        return t.source_trust_import
    return t.source_trust_unknown


def credibility_score(src: dict, attrs: dict, profile_type: str = "tech") -> float:
    """真实性 = (来源权重 + 权威加分) × 一致性乘子，clamp [0,1]。"""
    t = settings.thresholds
    base = _source_trust(src) + authority_bonus(attrs)
    base = max(0.0, min(1.0, base))
    return max(0.0, min(1.0, base * consistency_factor(profile_type, attrs)))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `py -3.12 -m pytest tests/ingest_ods/test_quality_rules.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/quality_rules.py tests/ingest_ods/test_quality_rules.py
git commit -m "feat(scoring): quality_rules 纯函数(时效/可信/一致性)+单测"
```

---

## Task 3: scorer.py 重写为 RuleScorer + 单测（TDD）

**Files:**
- Modify: `metaprofile/ingest_ods/services/scorer.py` (整体重写)
- Test: `tests/ingest_ods/test_scorer.py`

- [ ] **Step 1: 写失败测试**

Create `tests/ingest_ods/test_scorer.py`：

```python
import asyncio
from datetime import date, timedelta
from metaprofile.ingest_ods.services.scorer import RuleScorer


def test_score_returns_all_five_fields():
    s = RuleScorer()
    attrs = {"tech_name_cn": "量子计算", "tech_domain": ["量子"], "tech_summary": "x",
             "current_status": "emerging", "trend": "up", "tech_name_en": "q",
             "doi": "10.1/x"}
    src = [{"source_table": "ods_science_literature",
            "raw_payload": {"update_time": str(date.today() - timedelta(days=10))}}]
    out = asyncio.run(s.score("tech", attrs, src))
    for k in ("completeness", "veracity_score", "timeliness_score", "data_as_of", "dq_index"):
        assert k in out, f"missing {k}"
    assert 0 < out["completeness"] <= 1.0
    assert out["veracity_score"] > 0.8        # ods 0.9 + doi
    assert out["timeliness_score"] > 0.9      # 10 天前
    assert 0 < out["dq_index"] <= 1.0


def test_score_no_data_as_of_timeliness_zero():
    s = RuleScorer()
    out = asyncio.run(s.score("tech", {"tech_name_cn": "x"}, [{"source_table": "ods_y", "raw_payload": {}}]))
    assert out["timeliness_score"] == 0.0
    assert out["data_as_of"] is None


def test_dq_index_weighted():
    s = RuleScorer()
    # 全满分 → dq = 1.0
    attrs = {f: "v" for f in ["tech_name_cn","tech_name_en","tech_domain","tech_summary","current_status","trend"]}
    src = [{"source_table": "ods_x", "raw_payload": {"update_time": str(date.today())}}]
    out = asyncio.run(s.score("tech", attrs, src))
    assert abs(out["dq_index"] - 1.0) < 0.01
```

- [ ] **Step 2: 跑测试确认失败**

Run: `py -3.12 -m pytest tests/ingest_ods/test_scorer.py -v`
Expected: FAIL（`RuleScorer` 不存在）

- [ ] **Step 3: 重写 scorer.py**

整体替换 `metaprofile/ingest_ods/services/scorer.py`：

```python
"""阶段④ 数据质量评分（规则型，零 LLM，ISO 25012 对齐）。

返回 dict：completeness / veracity_score / timeliness_score / data_as_of / dq_index。
接口 score(profile_type, attrs, source_rows) 与原 LLM Scorer 一致 → orchestrator 零改。
"""
from __future__ import annotations

from datetime import date

import structlog

from metaprofile.foundation.enrichment.completeness import score_completeness
from metaprofile.ingest_ods.services.quality_rules import (
    credibility_score, timeliness_score,
)
from metaprofile.shared.config.settings import settings
from metaprofile.shared.schemas.base import EntityType

logger = structlog.get_logger(__name__)

# profile_type 字符串 → EntityType 枚举（score_completeness 需要）
_PT2ET = {
    "tech": EntityType.TECH, "org": EntityType.ORG,
    "person": EntityType.PERSON, "project": EntityType.PROJECT,
}


def _latest_as_of(source_rows: list[dict]) -> date | None:
    """取 source_rows 中最新 update_time/event_time 为 data_as_of。"""
    best: date | None = None
    for r in source_rows:
        rp = r.get("raw_payload", {}) if isinstance(r, dict) else {}
        for k in ("update_time", "event_time"):
            v = rp.get(k)
            if not v:
                continue
            try:
                d = date.fromisoformat(str(v)[:10])
            except Exception:
                continue
            if best is None or d > best:
                best = d
    return best


class RuleScorer:
    """确定性规则评分器（无 LLM 依赖）。"""

    def __init__(self, llm=None) -> None:  # llm 参数保留仅为接口兼容，忽略
        self._llm = llm

    async def score(self, profile_type: str, attrs: dict,
                    source_rows: list[dict]) -> dict:
        t = settings.thresholds
        et = _PT2ET.get(profile_type)
        completeness = score_completeness(et, attrs).score if et is not None else 0.0
        data_as_of = _latest_as_of(source_rows)
        veracity = credibility_score(source_rows[0] if source_rows else {}, attrs, profile_type)
        timeliness = timeliness_score(data_as_of)
        dq = (t.dq_weight_completeness * completeness
              + t.dq_weight_veracity * veracity
              + t.dq_weight_timeliness * timeliness)
        return {
            "completeness": round(completeness, 4),
            "veracity_score": round(veracity, 4),
            "timeliness_score": round(timeliness, 4),
            "data_as_of": data_as_of,
            "dq_index": round(dq, 4),
        }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `py -3.12 -m pytest tests/ingest_ods/test_scorer.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/scorer.py tests/ingest_ods/test_scorer.py
git commit -m "feat(scoring): RuleScorer 重写(规则型,零LLM,返 completeness+veracity+timeliness+dq_index)"
```

---

## Task 4: orchestrator 注入 RuleScorer + 兜底 dict

**Files:**
- Modify: `metaprofile/ingest_ods/services/orchestrator.py:78` (注入点在 sql_warehouse.py 构造，见下) + `metaprofile/ingest_ods/services/orchestrator.py:~192` (兜底 dict)

- [ ] **Step 1: 改 sql_warehouse 的 Scorer 注入**

`metaprofile/ingest_ods/collectors/sql_warehouse.py:79` 当前：
```python
        scorer=Scorer(llm=llm),
```
注：`Scorer` import 自哪？先确认：
Run: `grep -n "Scorer\|scorer" metaprofile/ingest_ods/collectors/sql_warehouse.py`
改为用 `RuleScorer`（无 llm）：

把该文件顶部 `from metaprofile.ingest_ods.services.scorer import Scorer`（若存在）改为：
```python
from metaprofile.ingest_ods.services.scorer import RuleScorer
```
并把 `scorer=Scorer(llm=llm)` 改为：
```python
        scorer=RuleScorer(),
```

- [ ] **Step 2: 改 orchestrator 兜底 dict（含 completeness/dq_index）**

`metaprofile/ingest_ods/services/orchestrator.py` 约 line 52（`_process_batch` 内 score 失败兜底）当前：
```python
                scores = {"veracity_score": 0.0, "timeliness_score": 0.0,
                          "data_as_of": None}
```
改为：
```python
                scores = {"completeness": 0.0, "veracity_score": 0.0,
                          "timeliness_score": 0.0, "data_as_of": None,
                          "dq_index": 0.0}
```

- [ ] **Step 3: py_compile**

Run: `python -m py_compile metaprofile/ingest_ods/collectors/sql_warehouse.py metaprofile/ingest_ods/services/orchestrator.py`
Expected: 无输出（OK）

- [ ] **Step 4: Commit**

```bash
git add metaprofile/ingest_ods/collectors/sql_warehouse.py metaprofile/ingest_ods/services/orchestrator.py
git commit -m "refactor(ingest_ods): 注入 RuleScorer + 兜底 dict 含 completeness/dq_index"
```

---

## Task 5: writer 落 completeness + dq_index

**Files:**
- Modify: `metaprofile/ingest_ods/services/writer.py:102-104`

- [ ] **Step 1: 读 writer 落分代码**

Run: `sed -n '90,110p' metaprofile/ingest_ods/services/writer.py`
确认现有：
```python
        merged["veracity_score"] = scores.get("veracity_score", 0.0)
        merged["timeliness_score"] = scores.get("timeliness_score", 0.0)
        merged["data_as_of"] = scores.get("data_as_of")
```

- [ ] **Step 2: 追加 completeness + dq_index**

在 `merged["data_as_of"] = scores.get("data_as_of")` 后加两行：
```python
        if scores.get("completeness") is not None:
            merged["completeness"] = scores.get("completeness")
        merged["dq_index"] = scores.get("dq_index", 0.0)
```

- [ ] **Step 3: py_compile + commit**

```bash
python -m py_compile metaprofile/ingest_ods/services/writer.py
git add metaprofile/ingest_ods/services/writer.py
git commit -m "feat(ingest_ods): writer 落 completeness + dq_index 到 ORM"
```

---

## Task 6: 4 画像 ORM 加 dq_index 列

**Files:**
- Modify: `metaprofile/profile_{tech,org,person,project}/domain/orm_models.py`（各 `timeliness_score` 行后）

- [ ] **Step 1: 4 文件各加 dq_index**

在每个 profile ORM 的 `timeliness_score: Mapped[float] = ...` 行之后追加：
```python
    dq_index: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
```
（tech 在 `profile_tech/domain/orm_models.py:58` 后；org `:60`；person `:63`；project `:66`）

- [ ] **Step 2: py_compile 4 文件**

Run: `python -m py_compile metaprofile/profile_tech/domain/orm_models.py metaprofile/profile_org/domain/orm_models.py metaprofile/profile_person/domain/orm_models.py metaprofile/profile_project/domain/orm_models.py`
Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add metaprofile/profile_*/domain/orm_models.py
git commit -m "feat(orm): 4 画像加 dq_index 列"
```

---

## Task 7: migration 0005 加 dq_index（4 表，has_column 守卫）

**Files:**
- Create: `migrations/versions/0005_dq_index.py`

- [ ] **Step 1: 参照 0004 格式新建 0005**

Create `migrations/versions/0005_dq_index.py`：

```python
"""profile 4 表加 dq_index 列（数据质量复合评分）

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("tech_profile", "org_profile", "person_profile", "project_profile")


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)
    for tbl in _TABLES:
        cols = {c["name"] for c in insp.get_columns(tbl)}
        if "dq_index" not in cols:
            op.add_column(tbl, sa.Column("dq_index", sa.Float(), nullable=False, server_default="0.0"))


def downgrade() -> None:
    for tbl in _TABLES:
        op.drop_column(tbl, "dq_index")
```

- [ ] **Step 2: py_compile**

Run: `python -m py_compile migrations/versions/0005_dq_index.py`
Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add migrations/versions/0005_dq_index.py
git commit -m "feat(db): migration 0005 加 dq_index 列(4 profile 表,has_column 守卫)"
```

---

## Task 8: 4 画像 response 暴露 dq_index

**Files:**
- Modify: `metaprofile/profile_{tech,org,person,project}/schemas/response.py`（各 `timeliness_score` 字段后）

- [ ] **Step 1: 4 文件各加 dq_index 字段**

在各 `*ProfileResponse` 的 `timeliness_score: float = Field(...)` 行后追加：
```python
    dq_index: float = Field(default=0.0, ge=0.0, le=1.0, description="数据质量综合评分(0-1)")
```
（tech `profile_tech/schemas/response.py:21` 后；org/person/project 对应 line 21 后）

- [ ] **Step 2: py_compile**

Run: `python -m py_compile metaprofile/profile_tech/schemas/response.py metaprofile/profile_org/schemas/response.py metaprofile/profile_person/schemas/response.py metaprofile/profile_project/schemas/response.py`
Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add metaprofile/profile_*/schemas/response.py
git commit -m "feat(api): 4 画像 response 暴露 dq_index"
```

---

## Task 9: 验证（重建 + migrate + ingest smoke）

- [ ] **Step 1: 重建 backend + 跑 migrate（加列）**

Run:
```bash
docker compose -f deploy/docker-compose.yml up -d --build backend
docker compose -f deploy/docker-compose.yml run --rm migrate
```
Expected: migrate 退出 0，`dq_index` 列已加（可 `docker exec metaprofile-postgres-1 psql -U metaprofile -d metaprofile -c "\d tech_profile" | grep dq_index`）

- [ ] **Step 2: 跑全套单测**

Run: `py -3.12 -m pytest tests/ -q 2>&1 | tail -5`
Expected: 全绿（含新 quality_rules + scorer 用例），无回归。

- [ ] **Step 3: 重跑 ingest smoke（science→tech, max_rows=3）**

更新 datasource 11 max_rows=3：
```bash
curl -s -X PUT http://localhost:8000/api/v1/settings/datasources/11 -H "Content-Type: application/json" \
  -d '{"config_json":{"db_connection_id":4,"table_set":["ods_science_literature"],"profile_types":["all"],"mode":"structured_only","enable_relations":false,"watermark_col":"update_time","batch_size":3,"workers":1,"max_rows":3}}' >/dev/null
# 清掉 science 已灌的 name: 卫星，强制重抽（可选）
TID=$(curl -s -X POST http://localhost:8000/api/v1/settings/collection/trigger/11 | python -c "import sys,json;print(json.load(sys.stdin)['task_id'])")
sleep 30
curl -s http://localhost:8000/api/v1/settings/collection/tasks/$TID | python -c "import sys,json;d=json.load(sys.stdin);print('status',d['status'],'imported',d['records_imported'],'err',d.get('error_msg'))"
```
Expected: status=completed imported=3 err 空。**关键：耗时 < 30s**（对比原 LLM ~90s/实体 × 3 ≈ 4.5min）。

- [ ] **Step 4: 断言新画像评分非 0**

```bash
docker exec metaprofile-postgres-1 psql -U metaprofile -d metaprofile -c \
  "SELECT tech_id, completeness, veracity_score, timeliness_score, dq_index FROM tech_profile WHERE tech_id LIKE 'name:%' ORDER BY created_at DESC LIMIT 3"
```
Expected: 3 行，**completeness/veracity_score/timeliness_score/dq_index 均 > 0**（不再归零）。veracity≈0.9（ODS 基线），timeliness 由 update_time 衰减。

- [ ] **Step 5: 提交收尾（若有未提交）+ push**

```bash
git status --short   # 确认无遗漏
git push origin main
```

---

## Self-Review

**Spec 覆盖**：
- §3.1 completeness（复用 score_completeness）→ Task 3 RuleScorer 调用 ✅
- §3.2 credibility（来源权重+权威+一致性）→ Task 2 quality_rules ✅
- §3.3 timeliness（指数衰减）→ Task 2 ✅
- §3.4 复合 dq_index → Task 3 RuleScorer ✅
- §4 RuleScorer 重写 + orchestrator 零改 + quality_rules 抽出 + settings 可调 → Task 1/3/4 ✅
- §4 dq_index 列 + migration → Task 6/7 ✅
- §4 response 暴露 → Task 8 ✅
- §6 测试（quality_rules/scorer）→ Task 2/3 TDD ✅
- §9 验收（ingest 毫秒、评分非 0）→ Task 9 ✅

**Placeholder 扫描**：无 TBD/TODO；每个代码步含完整代码；行号标注。

**类型一致**：`RuleScorer.score(profile_type:str, attrs, source_rows) -> dict` 与 orchestrator 调用 + writer 读取键名（completeness/veracity_score/timeliness_score/data_as_of/dq_index）全程一致；`quality_rules` 函数名（timeliness_score/credibility_score/consistency_factor/authority_bonus）Task2 定义与 Task3 引用一致。

**已知非阻塞**：`llm_call_log` 表缺（token meter warning）与本计划无关，留独立 migration。
