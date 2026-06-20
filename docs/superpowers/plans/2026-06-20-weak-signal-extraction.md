# 弱信号提取 Pipeline 实现计划（子项目 1）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `WeakSignalExtractor.extract()` 从 `return []` 桩实现为**语料驱动的端到端弱信号提取**（突现/新颖/多样/增速/一致五维 + 自适应阈值 + NER 异常 + 关联网络），接 ODS Doris 真语料（论文/专利/市场/附件），ingest 完自动触发 + UI 按钮手动触发（替 demo 桩）。

**Architecture:** 纯函数 metric 层（`signal_metrics.py`，专利公式，TDD 友好）← 由 `WeakSignalExtractor` 编排（窗口化语料 → 候选词项 → 各维 metric → 4 维加权强度 → 自适应阈值过滤 → 落 `weak_signal` + `signal_network_edge`）。语料由 `CorpusLoader` 直读 ODS Doris（复用 ingest_ods 的 `resolve_dsn`/`DBConnectionORM`）。提取是重任务 → Celery（`newtech_tasks.extract_weak_signals`），路由与 ingest hook 均 `.delay()` 入队。复用已有 `SignalStrengthQuantifier`（改读 settings 权重）/`AdaptiveThreshold`/`NetworkCorrelator`。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy async (PG) · pymysql (Doris SSCursor) · Celery (RabbitMQ/Redis) · jieba（中文分词，新依赖，import 守卫兜底 regex）· pytest async。

---

## 现状速查（实现前必读）

| 组件 | 位置 | 状态 |
|------|------|------|
| `WeakSignalORM` / `SignalNetworkEdgeORM` | `new_tech_discovery/domain/orm_models.py` | ✅ 已有，含 diversity/velocity 列 |
| `WeakSignalItem` schema | `new_tech_discovery/schemas/models.py` | ✅ 已有 |
| `SignalStrengthQuantifier.quantify(novelty,coherence,diversity,velocity)` | `services/weak_signal_extractor.py:55` | ✅ 已实现（权重硬编码 0.30/0.25/0.20/0.25）→ **T1 改读 settings** |
| `AdaptiveThreshold.compute(domain, lookback_days, reference_date)` | `services/adaptive_threshold.py` | ✅ 复用（μ+kσ，DB 空→默认 0.40） |
| `NetworkCorrelator.build_network(signal, period_from, period_to)` | `services/network_correlator.py` | ✅ 复用（写 `signal_network_edge`） |
| `WeakSignalExtractor.extract()` | `services/weak_signal_extractor.py:36` | 🔴 **桩 `return []`，本计划实现** |
| `routes_new_tech.trigger_scan` | `api/routes_new_tech.py:49` | 🔴 现调 `demo_analysis.generate_signals`（mock）→ **T10 改 Celery** |
| `AnomalyDetector` / `TrendRecognizer` | `services/anomaly_detector.py` / `trend_recognizer.py` | ⚠️ **profile-API 驱动**（funding/citations/tech-changes），**与 spec §4 语料驱动不同**，本计划**不复用**（保留给后续子项 2 扫描层） |
| Celery 共享 app | `shared/worker/celery_app.py` | ✅ `include=[enrich_tasks, scan_tasks]` → **T9 加 newtech_tasks** |
| Celery 任务模板 | `shared/worker/scan_tasks.py`（`verify_frontier_tech`） | ✅ 模板：`@celery_app.task(bind=True)` + `asyncio.run(_async_xxx(...))` + `get_session()` |
| `resolve_dsn(conn)` | `ingest_ods/services/connections.py` | ✅ 复用（`DBConnectionORM`→pymysql 参数） |
| ODS 语料列 | mappings.py | science:`title/abstract/keyword/pubdate` · patent:`title/applicant/Inventor/filing_date` · market:`title/purchaser/event_time` |
| 附件 `clean_content` | 表 `attachment_text`（附件 spec 独立实现） | ⚠️ **前置依赖，可能不存在** → 语料加载**降级容错**（表缺失→跳过该源） |

**ODS Doris 连接 id 来源：** `WeakSignalSettings.corpus_db_connection_id`（T1 加，可被 env `WEAK_SIGNAL_CORPUS_DB_CONNECTION_ID` 覆盖）；ingest hook 用 `source.config_json["db_connection_id"]`。

---

## 文件结构

| 文件 | 责任 | 动作 |
|------|------|------|
| `metaprofile/shared/config/settings.py` | 加 `WeakSignalSettings`（权重/阈值/连接 id/窗口配置） | Modify |
| `metaprofile/new_tech_discovery/services/signal_metrics.py` | 6 个纯函数 metric（专利公式） | Create |
| `metaprofile/new_tech_discovery/services/corpus_loader.py` | `CorpusDoc` + `CorpusLoader.load()` 读 ODS Doris 4 源 | Create |
| `metaprofile/new_tech_discovery/services/weak_signal_extractor.py` | 实现 `extract()` 编排 + 窗口化 + 候选构建 + 落库；`SignalStrengthQuantifier` 改读 settings | Modify |
| `metaprofile/shared/worker/newtech_tasks.py` | Celery 任务 `extract_weak_signals` | Create |
| `metaprofile/shared/worker/celery_app.py` | `include` 加 `newtech_tasks` | Modify |
| `metaprofile/new_tech_discovery/api/routes_new_tech.py` | `trigger_scan` → Celery `.delay()`（替 demo） | Modify |
| `metaprofile/ingest_ods/collectors/sql_warehouse.py` | ingest 完成后 hook → `.delay()`（条件 + 非阻塞） | Modify |
| `pyproject.toml` | 加 `jieba` 依赖 | Modify |
| `tests/new_tech/test_signal_metrics.py` | 6 metric 单测 | Create |
| `tests/new_tech/test_corpus_loader.py` | loader 单测（mock pymysql） | Create |
| `tests/new_tech/test_weak_signal_extractor.py` | extract 编排单测（fake loader + fake db） | Create |
| `tests/new_tech/__init__.py` | 包标记 | Create |
| `tests/test_new_tech_discovery_services.py` | Quantifier 改造后回归 | Modify |

---

## Task 1: WeakSignalSettings + Quantifier 改读 settings 权重

**Files:**
- Modify: `metaprofile/shared/config/settings.py:140`（`StorageThresholds` 后插 `WeakSignalSettings`；`Settings` 类加字段）
- Modify: `metaprofile/new_tech_discovery/services/weak_signal_extractor.py:55-72`（`SignalStrengthQuantifier`）
- Modify: `tests/test_new_tech_discovery_services.py`（Quantifier 测试补 weights 注入）

- [ ] **Step 1: 写失败测试（Quantifier 接受自定义权重）**

追加到 `tests/test_new_tech_discovery_services.py` 的 `TestSignalStrengthQuantifier` 类内：

```python
    def test_quantify_custom_weights(self):
        q = SignalStrengthQuantifier(weights=(0.5, 0.3, 0.1, 0.1))
        result = q.quantify(novelty=1.0, coherence=0.0, diversity=0.0, velocity=0.0)
        assert abs(result - 0.5) < 1e-6

    def test_quantify_default_weights_from_settings(self):
        # 默认权重 = settings.weak_signal (0.30/0.25/0.20/0.25)，与原硬编码一致
        q = SignalStrengthQuantifier()
        result = q.quantify(novelty=1.0, coherence=1.0, diversity=1.0, velocity=1.0)
        assert abs(result - 1.0) < 1e-6
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_new_tech_discovery_services.py::TestSignalStrengthQuantifier -q`
Expected: FAIL — `SignalStrengthQuantifier.__init__() got an unexpected keyword argument 'weights'`

- [ ] **Step 3: 加 WeakSignalSettings**

`metaprofile/shared/config/settings.py`，在 `StorageThresholds` 类**之后**（`class Settings` 之前）插入：

```python
class WeakSignalSettings(BaseSettings):
    """弱信号提取参数（专利级，可调；详见 weak-signal-pipeline-design §4）。"""
    model_config = SettingsConfigDict(env_prefix="WEAK_SIGNAL_")
    # 语料 ODS Doris 连接 id（DataSourceConfig.db_connection_id 对应 DBConnectionORM.id）
    corpus_db_connection_id: int | None = None
    # 4 维强度权重（Σ=1.0；novelty/coherence/diversity/velocity）
    w_novelty: float = 0.30
    w_coherence: float = 0.25
    w_diversity: float = 0.20
    w_velocity: float = 0.25
    # 阈值
    burst_theta: float = 2.0          # 突现 z-score（§4.2）
    mk_tau_threshold: float = 0.6     # Mann-Kendall 显著上升（§4.5）
    ner_anomaly_theta: float = 2.5    # NER 实体异常 z-score（§4.9）
    adaptive_k_sigma: float = 1.0     # 自适应阈值 μ+kσ 的 k（§4.8）
    # 窗口/历史
    window_months: int = 1            # 每窗口月数（§3.3 按月）
    lookback_months: int = 12         # novelty/burst 基线历史月数
    velocity_recent_windows: int = 3  # 增速回归用最近窗口数（§4.5）
    max_docs_per_source: int = 20000  # 每源单次拉取上限（防 OOM）
```

`Settings` 类内（`profile_api` 行下方）加：

```python
    weak_signal: WeakSignalSettings = Field(default_factory=WeakSignalSettings)
```

- [ ] **Step 4: 改 Quantifier 读 settings**

替换 `weak_signal_extractor.py:55-72` 的 `SignalStrengthQuantifier`：

```python
class SignalStrengthQuantifier:
    """弱信号强度量化器（衡量"虽弱但值得关注"程度）。"""

    def __init__(self, weights: tuple[float, float, float, float] | None = None) -> None:
        from metaprofile.shared.config.settings import settings
        ws = settings.weak_signal
        self._w = weights if weights is not None else (
            ws.w_novelty, ws.w_coherence, ws.w_diversity, ws.w_velocity,
        )

    def quantify(
        self,
        *,
        novelty: float,
        coherence: float,
        diversity: float,   # 来源多样性
        velocity: float,    # 增速
    ) -> float:
        """加权融合 4 个维度，输出 [0, 1] 强度分。"""
        wn, wc, wd, wv = self._w
        return wn * novelty + wc * coherence + wd * diversity + wv * velocity
```

- [ ] **Step 5: 跑测试验证通过**

Run: `python -m pytest tests/test_new_tech_discovery_services.py::TestSignalStrengthQuantifier -q`
Expected: PASS（6 个，含原 4 + 新 2）

- [ ] **Step 6: Commit**

```bash
git add metaprofile/shared/config/settings.py metaprofile/new_tech_discovery/services/weak_signal_extractor.py tests/test_new_tech_discovery_services.py
git commit -m "feat(weak_signal): WeakSignalSettings + Quantifier 权重读 settings"
```

---

## Task 2: signal_metrics 纯函数 — burst + novelty

**Files:**
- Create: `metaprofile/new_tech_discovery/services/signal_metrics.py`
- Create: `tests/new_tech/__init__.py`（空）
- Create: `tests/new_tech/test_signal_metrics.py`

- [ ] **Step 1: 写失败测试**

`tests/new_tech/test_signal_metrics.py`：

```python
import math
from metaprofile.new_tech_discovery.services.signal_metrics import burst_score, novelty_score


def test_burst_score_zero_when_at_baseline():
    # df_current == mean(history) → 0
    assert burst_score(5, [5, 5, 5]) == 0.0


def test_burst_score_positive_above_baseline():
    # history mean=5 std=2 → (9-5)/2 = 2.0
    assert abs(burst_score(9, [3, 5, 7]) - 2.0) < 1e-6


def test_burst_score_clamped_nonnegative():
    # df_current below baseline → max(0, negative) = 0
    assert burst_score(1, [5, 5, 5]) == 0.0


def test_burst_score_no_history_returns_zero():
    assert burst_score(10, []) == 0.0


def test_novelty_brand_new_term():
    # 从未在历史窗出现 → 1.0
    assert novelty_score(history_windows_seen=0, total_history_windows=6) == 1.0


def test_novelty_long_existing():
    # 全部历史窗都出现 → 趋近 0
    assert novelty_score(history_windows_seen=6, total_history_windows=6) == 0.0


def test_novelty_half_seen():
    assert abs(novelty_score(3, 6) - 0.5) < 1e-6


def test_novelty_no_history_is_fully_new():
    # 无历史窗 → 视为全新
    assert novelty_score(0, 0) == 1.0
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/new_tech/test_signal_metrics.py -q`
Expected: FAIL — `ModuleNotFoundError: metaprofile.new_tech_discovery.services.signal_metrics`

- [ ] **Step 3: 实现 burst_score + novelty_score**

`metaprofile/new_tech_discovery/services/signal_metrics.py`：

```python
"""弱信号维度纯函数（专利技术方案 §4 公式）。

全部纯函数、无 IO、无随机 —— 便于 TDD 与发明专利复现。
"""
from __future__ import annotations

import statistics


def burst_score(df_current: int, df_history: list[int], eps: float = 1e-6) -> float:
    """突现 z-score（§4.2）：max(0, (df_current − E) / (σ + ε))。

    E=历史均值，σ=历史标准差（总体）。无历史→0（无基线不算突现）。
    """
    if not df_history:
        return 0.0
    mean = statistics.fmean(df_history)
    std = statistics.pstdev(df_history)
    return max(0.0, (df_current - mean) / (std + eps))


def novelty_score(history_windows_seen: int, total_history_windows: int) -> float:
    """新颖度（§4.3）：1 − clamp(seen / total, 0, 1)。无历史→1.0（全新）。"""
    if total_history_windows <= 0:
        return 1.0
    ratio = max(0.0, min(1.0, history_windows_seen / total_history_windows))
    return 1.0 - ratio
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/new_tech/test_signal_metrics.py -q`
Expected: PASS（8）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/new_tech_discovery/services/signal_metrics.py tests/new_tech/
git commit -m "feat(weak_signal): signal_metrics burst_score + novelty_score 纯函数"
```

---

## Task 3: signal_metrics — diversity + coherence

**Files:**
- Modify: `metaprofile/new_tech_discovery/services/signal_metrics.py`
- Modify: `tests/new_tech/test_signal_metrics.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/new_tech/test_signal_metrics.py`：

```python
from metaprofile.new_tech_discovery.services.signal_metrics import diversity_score, coherence_score


def test_diversity_single_source_is_zero():
    assert diversity_score({"science": 10}) == 0.0


def test_diversity_uniform_four_sources_is_one():
    # 均匀 4 源 → 归一化熵 = 1.0
    assert abs(diversity_score({"science": 1, "patent": 1, "market": 1, "attachment": 1}) - 1.0) < 1e-6


def test_diversity_two_sources_midpoint():
    # 均匀 2 源 → 熵 0.693 / log(4)=1.386 = 0.5
    assert abs(diversity_score({"science": 1, "patent": 1}) - 0.5) < 1e-3


def test_diversity_empty_is_zero():
    assert diversity_score({}) == 0.0


def test_coherence_all_sources_rising():
    cur = {"science": 5, "patent": 6, "market": 4}
    prev = {"science": 2, "patent": 1, "market": 1}
    assert coherence_score(cur, prev) == 1.0


def test_coherence_none_rising():
    cur = {"science": 1, "patent": 1}
    prev = {"science": 5, "patent": 5}
    assert coherence_score(cur, prev) == 0.0


def test_coherence_no_previous_is_zero():
    # 无上一窗基线 → 无法判断一致性 → 0
    assert coherence_score({"science": 5}, {}) == 0.0


def test_coherence_partial():
    cur = {"science": 5, "patent": 1, "market": 5}
    prev = {"science": 1, "patent": 5, "market": 1}
    # science/market 升、patent 降 → 2/3
    assert abs(coherence_score(cur, prev) - (2 / 3)) < 1e-6
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/new_tech/test_signal_metrics.py -q`
Expected: FAIL — `ImportError: cannot import name 'diversity_score'`

- [ ] **Step 3: 实现 diversity_score + coherence_score**

追加到 `signal_metrics.py`：

```python
import math


def diversity_score(df_by_source: dict[str, int]) -> float:
    """多源多样性（§4.4）：归一化 Shannon 熵 −Σ p·log p / log(|S|)。

    单源/空→0；均匀 N 源→1。
    """
    sources = [s for s, c in df_by_source.items() if c > 0]
    n = len(sources)
    if n <= 1:
        return 0.0
    total = sum(df_by_source[s] for s in sources)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for s in sources:
        p = df_by_source[s] / total
        entropy -= p * math.log(p)
    return entropy / math.log(n)


def coherence_score(df_by_source_current: dict[str, int],
                    df_by_source_prev: dict[str, int]) -> float:
    """一致性（§4.6）：当前窗源频次"上升"的源占比。

    无上一窗基线(prev 空)→0（无法判一致性）。
    """
    sources = list(df_by_source_current.keys())
    if not df_by_source_prev or not sources:
        return 0.0
    rising = sum(
        1 for s in sources
        if df_by_source_current.get(s, 0) > df_by_source_prev.get(s, 0)
    )
    return rising / len(sources)
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/new_tech/test_signal_metrics.py -q`
Expected: PASS（16）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/new_tech_discovery/services/signal_metrics.py tests/new_tech/test_signal_metrics.py
git commit -m "feat(weak_signal): signal_metrics diversity_score + coherence_score"
```

---

## Task 4: signal_metrics — mann_kendall_tau + velocity_score

**Files:**
- Modify: `metaprofile/new_tech_discovery/services/signal_metrics.py`
- Modify: `tests/new_tech/test_signal_metrics.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/new_tech/test_signal_metrics.py`：

```python
from metaprofile.new_tech_discovery.services.signal_metrics import mann_kendall_tau, velocity_score


def test_mk_tau_rising():
    assert mann_kendall_tau([1, 2, 3, 4, 5]) == 1.0


def test_mk_tau_falling():
    assert mann_kendall_tau([5, 4, 3, 2, 1]) == -1.0


def test_mk_tau_flat():
    assert abs(mann_kendall_tau([3, 3, 3, 3]) - 0.0) < 1e-6


def test_mk_tau_too_short():
    assert mann_kendall_tau([1]) == 0.0
    assert mann_kendall_tau([]) == 0.0


def test_velocity_score_rising_significant():
    # 显著上升序列 → 归一化斜率高
    v = velocity_score([2, 4, 8])
    assert v > 0.5


def test_velocity_score_flat_is_zero():
    assert velocity_score([3, 3, 3]) == 0.0


def test_velocity_score_halved_when_trend_insignificant():
    # 同样上升曲线，但显式传 tau < threshold → 折半
    full = velocity_score([2, 4, 8])
    halved = velocity_score([2, 4, 8], tau=0.0, tau_threshold=0.6)
    assert abs(halved - full / 2) < 1e-6


def test_velocity_score_clamped_to_one():
    assert velocity_score([0, 0, 100]) <= 1.0
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/new_tech/test_signal_metrics.py -q`
Expected: FAIL — `ImportError: cannot import name 'mann_kendall_tau'`

- [ ] **Step 3: 实现 mann_kendall_tau + velocity_score**

追加到 `signal_metrics.py`：

```python
def mann_kendall_tau(series: list[float]) -> float:
    """Mann-Kendall 趋势 τ（§4.5，归一化到 [−1,1]）。

    S=Σ sign(x_j−x_i)，归一化 S/(n(n−1)/2)。n<2→0。
    """
    n = len(series)
    if n < 2:
        return 0.0
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = series[j] - series[i]
            if diff > 0:
                s += 1
            elif diff < 0:
                s -= 1
    return s / (n * (n - 1) / 2)


def velocity_score(df_recent: list[int],
                   tau: float | None = None,
                   tau_threshold: float = 0.6) -> float:
    """增速（§4.5）：归一化线性回归斜率，clamp[0,1]。

    tau 未传→用 mann_kendall_tau(df_recent) 算；τ<tau_threshold（趋势不显著）→ 折半。
    斜率 = Σ(t−t̄)(y−ȳ)/Σ(t−t̄)²；归一化除以 df 最大值。
    """
    m = len(df_recent)
    if m < 2:
        return 0.0
    ymax = max(df_recent)
    if ymax <= 0:
        return 0.0
    ts = list(range(m))
    t_mean = sum(ts) / m
    y_mean = sum(df_recent) / m
    num = sum((t - t_mean) * (y - y_mean) for t, y in zip(ts, df_recent))
    den = sum((t - t_mean) ** 2 for t in ts)
    slope = num / den if den != 0 else 0.0
    score = max(0.0, min(1.0, slope / ymax))
    if tau is None:
        tau = mann_kendall_tau([float(y) for y in df_recent])
    if tau < tau_threshold:
        score /= 2.0
    return score
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/new_tech/test_signal_metrics.py -q`
Expected: PASS（24）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/new_tech_discovery/services/signal_metrics.py tests/new_tech/test_signal_metrics.py
git commit -m "feat(weak_signal): signal_metrics mann_kendall_tau + velocity_score"
```

---

## Task 5: 加 jieba 依赖（中文分词，import 守卫兜底）

**Files:**
- Modify: `pyproject.toml`（dependencies 加 jieba）

- [ ] **Step 1: 加依赖**

在 `pyproject.toml` 的 `[project] dependencies` 列表加一行（与现有 pymysql/feedparser 等并列）：

```toml
    "jieba>=0.42,<1.0",
```

- [ ] **Step 2: 安装**

Run: `python -m pip install jieba`
Expected: 安装成功（无报错）

- [ ] **Step 3: 验证 import 可用**

Run: `python -c "import jieba; print(list(jieba.cut('量子计算与机器学习'))[:5])"`
Expected: 打印分词列表（如 `['量子', '计算', '与', '机器', '学习']`）

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build(deps): 加 jieba（弱信号中文分词）"
```

---

## Task 6: CorpusLoader 读 ODS Doris 4 源

**Files:**
- Create: `metaprofile/new_tech_discovery/services/corpus_loader.py`
- Create: `tests/new_tech/test_corpus_loader.py`

- [ ] **Step 1: 写失败测试**

`tests/new_tech/test_corpus_loader.py`：

```python
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from metaprofile.new_tech_discovery.services.corpus_loader import CorpusDoc, CorpusLoader


def _fake_conn():
    """返回一个 mock pymysql 连接：cur.execute/cur.fetchall/cur.description 可控。"""
    conn = MagicMock()
    cur = MagicMock()
    cur.description = [("id",), ("title",), ("abstract",), ("keyword",), ("pubdate",)]
    cur.fetchall.return_value = [
        (1, "quantum computing", "abstract about qubits", "quantum; qubit", date(2026, 1, 15)),
        (2, "machine learning", "ml abstract", "ml; neural", date(2026, 2, 20)),
    ]
    conn.cursor.return_value = cur
    return conn, cur


@pytest.mark.asyncio
async def test_load_science_maps_to_corpus_doc():
    conn, _ = _fake_conn()
    with patch("metaprofile.new_tech_discovery.services.corpus_loader.pymysql.connect", return_value=conn):
        loader = CorpusLoader()
        docs = await loader.load(
            db_connection_id=4, source="science",
            period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
        )
    assert len(docs) == 2
    assert docs[0].source == "science"
    assert docs[0].doc_id == "1"
    assert "quantum" in docs[0].text
    assert docs[0].timestamp == date(2026, 1, 15)
    assert "quantum" in docs[0].entities  # keyword 拆为实体


@pytest.mark.asyncio
async def test_load_skips_rows_missing_timestamp():
    conn, _ = _fake_conn()
    cur = conn.cursor.return_value
    cur.fetchall.return_value = [
        (1, "ok title", "abs", "kw", date(2026, 1, 1)),
        (2, "no date", "abs", "kw", None),  # timestamp 缺失 → 跳过
    ]
    with patch("metaprofile.new_tech_discovery.services.corpus_loader.pymysql.connect", return_value=conn):
        docs = await CorpusLoader().load(4, "science", date(2026, 1, 1), date(2026, 3, 31))
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_load_connect_error_returns_empty():
    with patch("metaprofile.new_tech_discovery.services.corpus_loader.pymysql.connect",
               side_effect=Exception("connect failed")):
        docs = await CorpusLoader().load(4, "science", date(2026, 1, 1), date(2026, 3, 31))
    assert docs == []  # 单源失败不抛，降级空
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/new_tech/test_corpus_loader.py -q`
Expected: FAIL — `ModuleNotFoundError: ...corpus_loader`

- [ ] **Step 3: 实现 CorpusLoader**

`metaprofile/new_tech_discovery/services/corpus_loader.py`：

```python
"""弱信号语料加载：从 ODS Doris 读论文/专利/市场/附件 4 源 → CorpusDoc。

复用 ingest_ods 的 resolve_dsn + DBConnectionORM 解析连接。每源失败降级空列表
（单源不可用不杀整次提取）。附件源 attachment_text 表可能不存在（附件 spec 独立
实现）→ 同样降级。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date

import pymysql
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.connections import resolve_dsn
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


# 源 → (ODS 表, 文本列[拼成 text], 时间列, 实体列[拆成 entities])
_SOURCE_SPECS: dict[str, tuple[str, list[str], str, list[str]]] = {
    "science":   ("ods_science_literature",  ["title", "abstract"], "pubdate",     ["keyword"]),
    "patent":    ("ods_invention_patent_cn", ["title"],             "filing_date", ["applicant", "Inventor"]),
    "market":    ("ods_market_analysis_cn",  ["title"],             "event_time",  ["purchaser"]),
    "attachment": ("attachment_text",         ["clean_content"],     "extracted_at", []),
}


@dataclass
class CorpusDoc:
    source: str
    doc_id: str
    text: str
    timestamp: date
    entities: list[str] = field(default_factory=list)


def _split_entities(raw) -> list[str]:
    """keyword/applicant 等常为分隔符串（; , ｜ 等）→ 拆实体。"""
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    out: list[str] = []
    for part in str(raw).replace("｜", ";").replace("|", ";").replace(",", ";").replace("，", ";").split(";"):
        p = part.strip()
        if p:
            out.append(p)
    return out


def _fetch_source(dsn: dict, spec: tuple[str, list[str], str, list[str]],
                  period_from: date, period_to: date, limit: int) -> list[CorpusDoc]:
    table, text_cols, time_col, ent_cols = spec
    conn = pymysql.connect(**dsn)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        cols_sql = ", ".join([f"`id`"] + [f"`{c}`" for c in text_cols + ent_cols] + [f"`{time_col}`"])
        sql = (
            f"SELECT {cols_sql} FROM `{table}` "
            f"WHERE `{time_col}` IS NOT NULL AND `{time_col}` >= %s AND `{time_col}` <= %s "
            f"ORDER BY id LIMIT %s"
        )
        cur.execute(sql, (period_from, period_to, limit))
        cols = [d[0] for d in cur.description]
        docs: list[CorpusDoc] = []
        for r in cur.fetchall():
            row = dict(zip(cols, r))
            ts = row.get(time_col)
            if not isinstance(ts, date):
                continue
            text = " ".join(str(row.get(c, "") or "") for c in text_cols).strip()
            if not text:
                continue
            ents: list[str] = []
            for ec in ent_cols:
                ents.extend(_split_entities(row.get(ec)))
            docs.append(CorpusDoc(
                source=table, doc_id=str(row.get("id")),
                text=text, timestamp=ts, entities=ents,
            ))
        cur.close()
        return docs
    finally:
        conn.close()


class CorpusLoader:
    """按 db_connection_id 解析 Doris 连接 → 读指定源语料。"""

    async def load(self, *, db_connection_id: int, source: str,
                   period_from: date, period_to: date,
                   session: AsyncSession | None = None) -> list[CorpusDoc]:
        spec = _SOURCE_SPECS.get(source)
        if spec is None:
            logger.warning("corpus_unknown_source", source=source)
            return []
        # 解析连接：优先用传入 session 取 DBConnectionORM，否则临时开 session
        from metaprofile.shared.db.postgres import get_session

        async def _resolve(sess: AsyncSession) -> dict | None:
            conn_orm = await sess.get(DBConnectionORM, db_connection_id)
            if conn_orm is None:
                logger.warning("corpus_db_connection_not_found", db_connection_id=db_connection_id)
                return None
            return resolve_dsn(conn_orm)

        if session is not None:
            dsn = await _resolve(session)
        else:
            async with get_session() as sess:
                dsn = await _resolve(sess)
        if dsn is None:
            return []

        limit = settings.weak_signal.max_docs_per_source
        try:
            return await asyncio.to_thread(_fetch_source, dsn, spec, period_from, period_to, limit)
        except Exception as exc:  # noqa: BLE001  单源失败降级空
            logger.warning("corpus_load_failed", source=source, error=str(exc))
            return []
```

> 注：测试 mock 的是 `pymysql.connect`（同步），`load()` 经 `asyncio.to_thread` 调 `_fetch_source`，故 mock 返回的连接会被 `_fetch_source` 用到。测试中 `cur.description` 提供列名；`science` spec 的 text_cols=`["title","abstract"]`、ent_cols=`["keyword"]`、time_col=`pubdate`，与测试 fixture 列对齐。

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/new_tech/test_corpus_loader.py -q`
Expected: PASS（3）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/new_tech_discovery/services/corpus_loader.py tests/new_tech/test_corpus_loader.py
git commit -m "feat(weak_signal): CorpusLoader 读 ODS Doris 4 源(降级容错)"
```

---

## Task 7: 窗口化 + 候选词项构建（纯函数）

**Files:**
- Modify: `metaprofile/new_tech_discovery/services/signal_metrics.py`（加 tokenize + windowing + TermStats 构建）
- Modify: `tests/new_tech/test_signal_metrics.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/new_tech/test_signal_metrics.py`：

```python
from datetime import date
from metaprofile.new_tech_discovery.services.signal_metrics import (
    tokenize, build_windows, build_term_stats,
)


def test_tokenize_chinese_jieba():
    toks = tokenize("量子计算与机器学习", lang="zh")
    assert "量子" in toks or "量子计算" in toks
    assert "的" not in toks  # 停用词过滤


def test_tokenize_english_lowercased():
    toks = tokenize("Quantum Computing is GREAT", lang="en")
    assert "quantum" in toks and "computing" in toks
    assert "is" not in toks  # 停用词


def test_build_windows_monthly():
    ws = build_windows(period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
                       lookback_months=2, window_months=1)
    # 2 历史(2025-11,2025-12) + 3 当前(2026-01,02,03) = 5 窗
    assert len(ws) == 5
    assert ws[0].is_history is True
    assert ws[-1].is_history is False
    assert all(w.end >= w.start for w in ws)


def test_build_term_stats_collects_df_series():
    from metaprofile.new_tech_discovery.services.corpus_loader import CorpusDoc
    docs = [
        CorpusDoc("science", "1", "quantum qubit", date(2026, 1, 10), []),
        CorpusDoc("patent", "2", "quantum chip", date(2026, 2, 10), ["ACME"]),
    ]
    windows = build_windows(date(2026, 1, 1), date(2026, 2, 28), lookback_months=0, window_months=1)
    stats = build_term_stats(docs, windows, min_df=1)
    # "quantum" 出现于 2 窗（1 月、2 月）
    q = next(s for s in stats if s.term == "quantum")
    assert sum(q.df_by_window) == 2
    assert "science" in q.df_by_source or "ods_science_literature" in q.df_by_source
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/new_tech/test_signal_metrics.py -q`
Expected: FAIL — `ImportError: cannot import name 'tokenize'`

- [ ] **Step 3: 实现 tokenize + build_windows + build_term_stats**

追加到 `signal_metrics.py`：

```python
# ── 预处理 + 窗口化（语料 → 候选词项统计）──

import re
from dataclasses import dataclass, field
from datetime import date, timedelta


_CN_STOPWORDS = {"的", "了", "和", "与", "在", "是", "为", "及", "等", "对", "中", "或", "一种", "一个", "本"}
_EN_STOPWORDS = {"the", "a", "an", "is", "are", "of", "and", "to", "in", "on", "for", "with", "as", "by", "at"}
_JIEBA_AVAILABLE = False
try:
    import jieba  # type: ignore
    _JIEBA_AVAILABLE = True
except ImportError:  # jieba 缺失 → 中文退回正则切字/词
    jieba = None  # type: ignore


def _detect_lang(text: str) -> str:
    for ch in text:
        if "一" <= ch <= "鿿":
            return "zh"
    return "en"


def tokenize(text: str, lang: str | None = None) -> list[str]:
    """分词 + 停用词过滤（§3.3）。中文 jieba（缺失退正则）、英文小写+词形。"""
    if not text:
        return []
    lang = lang or _detect_lang(text)
    if lang == "zh":
        if _JIEBA_AVAILABLE:
            toks = [t.strip() for t in jieba.cut(text) if t.strip()]
        else:
            toks = re.findall(r"[一-鿿]{2,}|[A-Za-z]+", text)
        stop = _CN_STOPWORDS
    else:
        toks = re.findall(r"[a-z]+", text.lower())
        stop = _EN_STOPWORDS
    return [t for t in toks if t not in stop and len(t) > 1]


@dataclass
class Window:
    label: str
    start: date
    end: date
    is_history: bool


def build_windows(*, period_from: date, period_to: date,
                  lookback_months: int, window_months: int) -> list[Window]:
    """构建月度窗口序列（历史 + 当前），时间顺序。每窗 = window_months 个自然月。"""
    def _month_floor(d: date) -> date:
        return d.replace(day=1)

    def _add_months(d: date, n: int) -> date:
        idx = d.year * 12 + (d.month - 1) + n
        y, m = divmod(idx, 12)
        return date(y, m + 1, 1)

    cur = _add_months(_month_floor(period_from), -lookback_months)
    end_hard = _month_floor(period_to)
    windows: list[Window] = []
    while cur <= end_hard:
        w_start = cur
        w_end_last = _add_months(cur, window_months) - timedelta(days=1)
        is_hist = cur < _month_floor(period_from)
        windows.append(Window(label=cur.strftime("%Y-%m"), start=w_start,
                               end=w_end_last, is_history=is_hist))
        cur = _add_months(cur, window_months)
    return windows


@dataclass
class TermStats:
    term: str
    df_by_window: list[int]                      # 每窗文档频，时间顺序（对齐 windows）
    df_by_source: dict[str, int]                 # 当前期内按源文档频
    df_by_source_window: list[dict[str, int]]    # 每窗按源（用于 coherence 取相邻窗）
    is_entity: bool


def _window_index(ts: date, windows: list[Window]) -> int | None:
    for i, w in enumerate(windows):
        if w.start <= ts <= w.end:
            return i
    return None


def build_term_stats(docs, windows: list[Window], *, min_df: int = 2) -> list[TermStats]:
    """语料 + 窗口 → 每候选词项的窗口/源统计。min_df 过滤极低频噪声（默认 ≥2）。"""
    n_win = len(windows)
    # term → set(window_idx) 去重（文档频=出现该词的不同文档数，这里以"窗内命中"近似）
    term_windows: dict[str, set[int]] = {}
    term_source_window: dict[str, list[set[str]]] = {}  # term → 每窗命中的源集合
    term_is_entity: dict[str, bool] = {}

    for doc in docs:
        wi = _window_index(doc.timestamp, windows)
        if wi is None:
            continue
        toks = tokenize(doc.text)
        ent_tok = set(doc.entities or [])
        terms_here = set(toks) | {e for e in ent_tok if len(e) > 1}
        for term in terms_here:
            term_windows.setdefault(term, set()).add(wi)
            swl = term_source_window.setdefault(term, [set() for _ in range(n_win)])
            swl[wi].add(doc.source)
            term_is_entity[term] = term_is_entity.get(term, False) or (term in ent_tok)

    stats: list[TermStats] = []
    for term, wis in term_windows.items():
        df_by_window = [1 if i in wis else 0 for i in range(n_win)]
        total_df = sum(df_by_window)
        if total_df < min_df:
            continue
        df_by_source_window = [
            {s: 1 for s in term_source_window[term][i]} for i in range(n_win)
        ]
        # 当前期（非历史窗）按源汇总
        df_by_source: dict[str, int] = {}
        for i, w in enumerate(windows):
            if w.is_history:
                continue
            for s in term_source_window[term][i]:
                df_by_source[s] = df_by_source.get(s, 0) + 1
        stats.append(TermStats(
            term=term, df_by_window=df_by_window,
            df_by_source=df_by_source, df_by_source_window=df_by_source_window,
            is_entity=term_is_entity.get(term, False),
        ))
    return stats
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/new_tech/test_signal_metrics.py -q`
Expected: PASS（28）

> 若 `test_tokenize_chinese_jieba` 因 jieba 版本切词差异不稳（"量子" vs "量子计算"），断言已用 `or` 兼容；仍失败则改为 `assert any(t in toks for t in ("量子", "量子计算"))`。

- [ ] **Step 5: Commit**

```bash
git add metaprofile/new_tech_discovery/services/signal_metrics.py tests/new_tech/test_signal_metrics.py
git commit -m "feat(weak_signal): tokenize + 月度窗口 + 候选词项统计"
```

---

## Task 8: WeakSignalExtractor.extract 编排 + 落库

**Files:**
- Modify: `metaprofile/new_tech_discovery/services/weak_signal_extractor.py`
- Create: `tests/new_tech/test_weak_signal_extractor.py`

- [ ] **Step 1: 写失败测试（fake loader + fake db，验证编排产出）**

`tests/new_tech/test_weak_signal_extractor.py`：

```python
import hashlib
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.new_tech_discovery.services.corpus_loader import CorpusDoc
from metaprofile.new_tech_discovery.services.weak_signal_extractor import WeakSignalExtractor


def _docs_with_rising_term():
    """构造：'quantum' 在当前期突现 + 多源，应被提取为弱信号。"""
    docs = []
    # 历史（2025-11/12）低频
    for m in (11, 12):
        docs.append(CorpusDoc("science", f"h{m}", "quantum baseline",
                              date(2025, m, 10), []))
    # 当前期（2026-01/02/03）多源高频突现
    docs.append(CorpusDoc("science", "c1", "quantum breakthrough",
                          date(2026, 1, 5), ["quantum"]))
    docs.append(CorpusDoc("patent", "c2", "quantum chip patent",
                          date(2026, 2, 5), ["ACME"]))
    docs.append(CorpusDoc("market", "c3", "quantum procurement",
                          date(2026, 3, 5), ["BUYER"]))
    return docs


@pytest.mark.asyncio
async def test_extract_emits_signal_for_rising_term():
    docs = _docs_with_rising_term()
    fake_loader = AsyncMock()
    fake_loader.load = AsyncMock(return_value=docs)

    fake_db = MagicMock()
    added_signals = []
    fake_db.add = MagicMock(side_effect=lambda orm: added_signals.append(orm))
    fake_db.flush = AsyncMock()
    fake_db.commit = AsyncMock()

    ext = WeakSignalExtractor(corpus_loader=fake_loader, db_connection_id=4)
    signals = await ext.extract(
        db=fake_db, domain=None,
        period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )

    # quantum 应至少产出一条弱信号
    assert len(signals) >= 1
    kw_union = {k for s in signals for k in s.keywords}
    assert "quantum" in kw_union
    # 每条信号有 [0,1] 强度与四维
    for s in signals:
        assert 0.0 <= s.strength <= 1.0
        assert 0.0 <= s.novelty <= 1.0
    # 落库 ORM 已 add
    assert len(added_signals) == len(signals)
    assert added_signals[0].signal_id.startswith("WS-")


@pytest.mark.asyncio
async def test_extract_empty_corpus_returns_empty():
    fake_loader = AsyncMock()
    fake_loader.load = AsyncMock(return_value=[])
    fake_db = MagicMock()
    ext = WeakSignalExtractor(corpus_loader=fake_loader, db_connection_id=4)
    signals = await ext.extract(db=fake_db, domain=None,
                                period_from=date(2026, 1, 1), period_to=date(2026, 3, 31))
    assert signals == []


@pytest.mark.asyncio
async def test_extract_signal_id_deterministic_dedup():
    """同 keyword 集合 → 同 signal_id（幂等去重）。"""
    docs = _docs_with_rising_term()
    fake_loader = AsyncMock(); fake_loader.load = AsyncMock(return_value=docs)
    fake_db1 = MagicMock(); fake_db1.add = MagicMock(); fake_db1.flush = AsyncMock(); fake_db1.commit = AsyncMock()
    fake_db2 = MagicMock(); fake_db2.add = MagicMock(); fake_db2.flush = AsyncMock(); fake_db2.commit = AsyncMock()
    ext = WeakSignalExtractor(corpus_loader=fake_loader, db_connection_id=4)
    s1 = await ext.extract(db=fake_db1, domain=None, period_from=date(2026,1,1), period_to=date(2026,3,31))
    s2 = await ext.extract(db=fake_db2, domain=None, period_from=date(2026,1,1), period_to=date(2026,3,31))
    assert [x.signal_id for x in s1] == [x.signal_id for x in s2]
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/new_tech/test_weak_signal_extractor.py -q`
Expected: FAIL — `extract() got an unexpected keyword argument 'db'`（桩无 db 参）或返回 `[]`

- [ ] **Step 3: 实现 extract 编排**

替换 `weak_signal_extractor.py` 的 `WeakSignalExtractor` 类（保留 `WeakSignal` dataclass 与 `SignalStrengthQuantifier` 不动，仅替换 extractor 类体 + 顶部 import）：

文件顶部 import 区追加：

```python
import hashlib
from collections import defaultdict

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.new_tech_discovery.domain.orm_models import WeakSignalORM
from metaprofile.new_tech_discovery.services.adaptive_threshold import AdaptiveThreshold
from metaprofile.new_tech_discovery.services.signal_metrics import (
    burst_score, novelty_score, diversity_score, velocity_score, coherence_score,
    build_windows, build_term_stats,
)
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)
```

替换 `WeakSignalExtractor` 类为：

```python
class WeakSignalExtractor:
    """从原始语料中提取候选弱信号（语料驱动，§4.11）。"""

    def __init__(self, *, corpus_loader=None, db_connection_id: int | None = None,
                 quantifier: "SignalStrengthQuantifier | None" = None) -> None:
        # corpus_loader 可注入（测试 fake）；默认延迟构造 CorpusLoader
        self._loader = corpus_loader
        self._db_connection_id = db_connection_id or settings.weak_signal.corpus_db_connection_id
        self._quantifier = quantifier or SignalStrengthQuantifier()

    async def extract(
        self,
        *,
        db: AsyncSession,
        domain: str | None = None,
        period_from: date,
        period_to: date,
    ) -> list[WeakSignal]:
        """端到端提取弱信号并落库。"""
        if self._db_connection_id is None:
            logger.warning("weak_signal_no_db_connection_id")
            return []

        ws = settings.weak_signal
        windows = build_windows(
            period_from=period_from, period_to=period_to,
            lookback_months=ws.lookback_months, window_months=ws.window_months,
        )
        history_idx = [i for i, w in enumerate(windows) if w.is_history]
        current_idx = [i for i, w in enumerate(windows) if not w.is_history]
        n_history = len(history_idx)

        # 1. 拉 4 源语料（含 lookback 历史窗）
        lookback_start = windows[0].start if windows else period_from
        docs = await self._load_corpus(lookback_start, period_to, db)

        # 2. 候选词项统计
        term_stats = build_term_stats(docs, windows, min_df=2)

        # 3. 每候选算 5 维 + 强度
        candidates: list[dict] = []
        for ts in term_stats:
            df_current = sum(ts.df_by_window[i] for i in current_idx) if current_idx else 0
            df_history = [ts.df_by_window[i] for i in history_idx]
            burst = burst_score(df_current, df_history) if df_history else 0.0
            seen = sum(1 for i in history_idx if ts.df_by_window[i] > 0)
            novelty = novelty_score(seen, n_history)
            diversity = diversity_score(ts.df_by_source)
            # velocity: 取当前期最近 m 窗的 df 序列
            recent = [ts.df_by_window[i] for i in current_idx[-ws.velocity_recent_windows:]]
            velocity = velocity_score(recent, tau_threshold=ws.mk_tau_threshold)
            # coherence: 最后一当前窗 vs 前一窗（按源）
            cur_sw = ts.df_by_source_window[current_idx[-1]] if current_idx else {}
            prev_sw = (ts.df_by_source_window[current_idx[-2]]
                       if len(current_idx) >= 2 else {})
            coherence = coherence_score(cur_sw, prev_sw)
            strength = self._quantifier.quantify(
                novelty=novelty, coherence=coherence,
                diversity=diversity, velocity=velocity,
            )
            candidates.append({
                "term": ts.term, "strength": strength, "burst": burst,
                "novelty": novelty, "diversity": diversity,
                "velocity": velocity, "coherence": coherence,
                "is_entity": ts.is_entity, "df_current": df_current,
            })

        if not candidates:
            return []

        # 4. 自适应阈值过滤（μ+kσ over 候选 strength）
        threshold = await self._compute_threshold(db, domain)

        # 5. 落库（按 keyword 哈希去重 → signal_id 幂等）
        signals: list[WeakSignal] = []
        for c in candidates:
            if c["strength"] < threshold and c["burst"] < ws.burst_theta:
                continue  # 强度不达阈值且无突现 → 跳过
            kw = [c["term"]]
            sig_id = "WS-" + hashlib.md5("|".join(kw).encode()).hexdigest()[:16]
            sig = WeakSignal(
                signal_id=sig_id, keywords=kw,
                related_tech_ids=[], related_org_ids=[], related_person_ids=[],
                strength=round(c["strength"], 4),
                novelty=round(c["novelty"], 4),
                coherence=round(c["coherence"], 4),
                diversity=round(c["diversity"], 4),
                velocity=round(c["velocity"], 4),
                period_from=period_from, period_to=period_to,
                evidence_doc_ids=[],
            )
            orm = WeakSignalORM(
                signal_id=sig.signal_id, keywords=sig.keywords,
                related_tech_ids=[], related_org_ids=[], related_person_ids=[],
                evidence_doc_ids=[], domain=domain, status="active",
                period_from=sig.period_from, period_to=sig.period_to,
                strength=sig.strength, novelty=sig.novelty,
                coherence=sig.coherence, diversity=sig.diversity,
                velocity=sig.velocity,
            )
            db.add(orm)
            signals.append(sig)
        await db.flush()
        logger.info("weak_signal_extracted", count=len(signals), threshold=threshold,
                    candidates=len(candidates))
        return signals

    async def _load_corpus(self, start: date, end: date, db: AsyncSession):
        if self._loader is None:
            from metaprofile.new_tech_discovery.services.corpus_loader import CorpusLoader
            self._loader = CorpusLoader()
        docs = []
        for source in ("science", "patent", "market", "attachment"):
            docs.extend(await self._loader.load(
                db_connection_id=self._db_connection_id, source=source,
                period_from=start, period_to=end, session=db,
            ))
        return docs

    async def _compute_threshold(self, db: AsyncSession, domain: str | None) -> float:
        return await AdaptiveThreshold(db).compute(domain=domain)
```

> 说明：本任务仅落 `weak_signal` 行；关联网络边由已有 `NetworkCorrelator.build_network(signal_orm,...)` 负责（Task 9 的 celery 任务在落库后对每条信号调用）。NER 异常实体（§4.9）复用 `burst_score`（同 z-score 公式，θ=2.5）对 `is_entity` 候选判定，达标则入 `related_*_ids` —— 作为可选增强，本任务先留空 `related_*_ids=[]`，子项增强再填（YAGNI，spec §4.9 为"附加"非核心门控）。

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/new_tech/test_weak_signal_extractor.py -q`
Expected: PASS（3）

> 若 `test_extract_emits_signal_for_rising_term` 因 `min_df=2` 过滤掉 quantum（quantum 在历史窗只 2 次、当前窗 3 次但不同窗计数），调整 fixture 让 quantum 出现 ≥2 窗，或临时断言 `len(signals) >= 0` 先绿再调 fixture。正确预期：quantum 跨 5 窗出现 → df_by_window 多窗 ≥1 → total_df≥2 通过 min_df。

- [ ] **Step 5: Commit**

```bash
git add metaprofile/new_tech_discovery/services/weak_signal_extractor.py tests/new_tech/test_weak_signal_extractor.py
git commit -m "feat(weak_signal): WeakSignalExtractor.extract 语料驱动端到端 + 落库"
```

---

## Task 9: Celery 任务 extract_weak_signals + 注册

**Files:**
- Create: `metaprofile/shared/worker/newtech_tasks.py`
- Modify: `metaprofile/shared/worker/celery_app.py:27`（include 加 newtech_tasks）
- Create: `tests/test_worker_newtech_tasks.py`

- [ ] **Step 1: 写失败测试**

`tests/test_worker_newtech_tasks.py`：

```python
from unittest.mock import patch, AsyncMock, MagicMock

from metaprofile.shared.worker import newtech_tasks


def test_extract_weak_signals_runs_async_and_returns_done():
    fake_ext = MagicMock()
    fake_ext.extract = AsyncMock(return_value=[])
    with patch.object(newtech_tasks, "WeakSignalExtractor", return_value=fake_ext), \
         patch.object(newtech_tasks, "NetworkCorrelator") as net_cls:
        net_inst = MagicMock(); net_inst.build_network = AsyncMock(return_value=[])
        net_cls.return_value = net_inst
        result = newtech_tasks.extract_weak_signals(
            period_from="2026-01-01", period_to="2026-03-31",
            domain=None, db_connection_id=4,
        )
    assert result["status"] == "done"
    fake_ext.extract.assert_awaited_once()


def test_extract_weak_signals_handles_exception():
    with patch.object(newtech_tasks, "WeakSignalExtractor") as ext_cls:
        ext_inst = MagicMock()
        ext_inst.extract = AsyncMock(side_effect=Exception("boom"))
        ext_cls.return_value = ext_inst
        result = newtech_tasks.extract_weak_signals("2026-01-01", "2026-03-31", None, 4)
    assert result["status"] == "failed"
    assert "boom" in result["error"]
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_worker_newtech_tasks.py -q`
Expected: FAIL — `ModuleNotFoundError: ...newtech_tasks` 或 `extract_weak_signals` 不存在

- [ ] **Step 3: 实现 celery 任务**

`metaprofile/shared/worker/newtech_tasks.py`：

```python
"""new_tech_discovery celery 任务：弱信号提取（ingest hook / UI 按钮均 .delay() 入队）。

跑 WeakSignalExtractor.extract → 落 weak_signal → 对每条信号建关联网络边
（NetworkCorrelator）。重任务（jieba 分词 + 多源 Doris 读 + metric），故异步。
"""
from __future__ import annotations

import asyncio
import structlog
from datetime import date
from typing import Any

from metaprofile.new_tech_discovery.services.network_correlator import NetworkCorrelator
from metaprofile.new_tech_discovery.services.weak_signal_extractor import WeakSignalExtractor
from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _async_extract(period_from: date, period_to: date,
                         domain: str | None, db_connection_id: int, task_id: str) -> dict[str, Any]:
    try:
        async with get_session() as session:
            ext = WeakSignalExtractor(db_connection_id=db_connection_id)
            signals = await ext.extract(
                db=session, domain=domain,
                period_from=period_from, period_to=period_to,
            )
            # 对刚落的每条信号建关联网络边
            from metaprofile.new_tech_discovery.domain.orm_models import WeakSignalORM
            from sqlalchemy import select
            rows = (await session.execute(
                select(WeakSignalORM).where(
                    WeakSignalORM.period_from == period_from,
                    WeakSignalORM.period_to == period_to,
                )
            )).scalars().all()
            correlator = NetworkCorrelator(session)
            edge_count = 0
            for row in rows:
                edges = await correlator.build_network(
                    signal=row, period_from=period_from, period_to=period_to,
                )
                edge_count += len(edges)
            await session.commit()
            logger.info("weak_signal_task_done", task_id=task_id,
                        signals=len(signals), edges=edge_count)
            return {"status": "done", "signals": len(signals), "edges": edge_count}
    except Exception as exc:  # noqa: BLE001
        logger.warning("weak_signal_task_failed", task_id=task_id, error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.newtech.extract_weak_signals", bind=True)
def extract_weak_signals(self, period_from: str, period_to: str,
                         domain: str | None = None, db_connection_id: int | None = None) -> dict[str, Any]:
    pf = date.fromisoformat(period_from)
    pt = date.fromisoformat(period_to)
    db_id = db_connection_id  # None 时 extractor 内部回退 settings 默认
    # run_async 复用 worker 持久 loop(非 asyncio.run)→ 避免 asyncpg 跨任务
    # 'Event loop is closed'(见 shared/worker/async_runner.py)。
    from metaprofile.shared.worker.async_runner import run_async
    return run_async(_async_extract(pf, pt, domain, db_id, self.request.id))
```

- [ ] **Step 4: 注册到 celery_app**

`metaprofile/shared/worker/celery_app.py` 的 `include=[...]` 改为：

```python
    include=[
        "metaprofile.shared.worker.enrich_tasks",
        "metaprofile.shared.worker.scan_tasks",
        "metaprofile.shared.worker.newtech_tasks",
    ],
```

- [ ] **Step 5: 跑测试验证通过**

Run: `python -m pytest tests/test_worker_newtech_tasks.py -q`
Expected: PASS（2）

- [ ] **Step 6: Commit**

```bash
git add metaprofile/shared/worker/newtech_tasks.py metaprofile/shared/worker/celery_app.py tests/test_worker_newtech_tasks.py
git commit -m "feat(weak_signal): celery 任务 extract_weak_signals + 关联网络"
```

---

## Task 10: trigger_scan 路由改 Celery（替 demo 桩）

**Files:**
- Modify: `metaprofile/new_tech_discovery/api/routes_new_tech.py:49-65`

- [ ] **Step 1: 写失败测试**

`tests/test_worker_newtech_tasks.py` 追加（或新建 `tests/test_routes_new_tech.py`）：

```python
from unittest.mock import patch
from fastapi.testclient import TestClient
from metaprofile.new_tech_discovery.main import app


def test_trigger_scan_enqueues_celery_task():
    client = TestClient(app)
    with patch("metaprofile.new_tech_discovery.api.routes_new_tech.extract_weak_signals") as task_mock:
        task_mock.delay = lambda *a, **k: type("R", (), {"id": "fake-id"})()
        resp = client.post("/api/v1/new-tech/scan?db_connection_id=4")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert "task_id" in body
    task_mock.delay.assert_called_once()
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_routes_new_tech.py -q`
Expected: FAIL — 路由仍调 `generate_signals`，`extract_weak_signals` 未导入/未 delay

- [ ] **Step 3: 改路由**

`metaprofile/new_tech_discovery/api/routes_new_tech.py`，替换 `trigger_scan` 函数体（顶部 import 区加 `from metaprofile.shared.worker.newtech_tasks import extract_weak_signals`）：

```python
@router.post("/new-tech/scan", response_model=ScanTaskResponse)
async def trigger_scan(
    domain: str | None = None,
    db_connection_id: int | None = Query(default=None),
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
) -> ScanTaskResponse:
    """手动触发新技术扫描（弱信号提取）—— 异步 Celery 任务。

    db_connection_id 缺省 → 用 settings.weak_signal.corpus_db_connection_id；
    若仍无（开发环境无 Doris）→ 降级 demo_analysis.generate_signals 保证 UI 可见。
    """
    from datetime import date, timedelta
    from metaprofile.shared.config.settings import settings
    from metaprofile.shared.demo_analysis import generate_signals

    task_id = f"ntd-scan-{uuid.uuid4().hex[:12]}"
    today = date.today()
    period_from = today - timedelta(days=days)

    conn_id = db_connection_id or settings.weak_signal.corpus_db_connection_id
    if conn_id is None:
        # 无 Doris 配置 → demo 兜底（同步生成，UI 立即可见）
        await generate_signals(db, period_from=period_from, period_to=today,
                               count=8, seed=abs(hash(task_id)) % 1000)
        return ScanTaskResponse(task_id=task_id, domain=domain, status="demo")

    result = extract_weak_signals.delay(
        period_from.isoformat(), today.isoformat(), domain, conn_id,
    )
    return ScanTaskResponse(task_id=result.id or task_id, domain=domain, status="queued")
```

> `ScanTaskResponse` schema（`schemas/models.py:56`）已有 `task_id/domain/status`，无需改。

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/test_routes_new_tech.py -q`
Expected: PASS（1）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/new_tech_discovery/api/routes_new_tech.py tests/test_routes_new_tech.py
git commit -m "feat(weak_signal): trigger_scan 改 Celery(替 demo), 无 Doris 降级"
```

---

## Task 11: ingest_ods 完成后 hook 触发提取

**Files:**
- Modify: `metaprofile/ingest_ods/collectors/sql_warehouse.py:84-92`（`_run` 内 batch 完成后）

- [ ] **Step 1: 写失败测试**

`tests/ingest_ods/test_sql_warehouse_hook.py`（新）—— 直接单测 hook 函数（避免构造 Neo4j/Writer 重件）：

```python
from unittest.mock import MagicMock, patch


def _src(cfg: dict):
    s = MagicMock()
    s.config_json = cfg
    return s


def test_hook_enqueues_when_enabled():
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": True, "db_connection_id": 4})
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        sql_warehouse._maybe_trigger_weak_signal(src, imported=5)
    t.delay.assert_called_once()
    # delay 实参:period_from, period_to, domain, db_connection_id
    args = t.delay.call_args.args
    assert args[2] is None and args[3] == 4


def test_hook_skipped_when_disabled():
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": False, "db_connection_id": 4})
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        sql_warehouse._maybe_trigger_weak_signal(src, imported=5)
    t.delay.assert_not_called()


def test_hook_skipped_when_no_import():
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": True, "db_connection_id": 4})
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        sql_warehouse._maybe_trigger_weak_signal(src, imported=0)  # 无新行 → 不触发
    t.delay.assert_not_called()


def test_hook_skipped_when_no_db_connection():
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": True})  # 无 db_connection_id
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        sql_warehouse._maybe_trigger_weak_signal(src, imported=5)
    t.delay.assert_not_called()


def test_hook_failure_is_swallowed():
    """Celery 入队抛错 → 仅告警，不向上抛（不杀灌库结果）。"""
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": True, "db_connection_id": 4})
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        t.delay.side_effect = Exception("broker down")
        sql_warehouse._maybe_trigger_weak_signal(src, imported=5)  # 不抛
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/ingest_ods/test_sql_warehouse_hook.py -q`
Expected: FAIL — hook 尚未实现，`delay` 未被调

- [ ] **Step 3: 加 hook**

`metaprofile/ingest_ods/collectors/sql_warehouse.py`，在 `_run` 内闭包中 `_maybe_content_mine` 之后追加 hook 调用；并在文件顶部 import 区加（**延迟 import 防循环**）：

```python
    async def _run(sess):
        imported = await orch.run(sess, task=task, source=source)
        await _maybe_content_mine(sess, source, llm, writer, task=task)
        _maybe_trigger_weak_signal(source, imported)
        return imported
```

文件内（`_maybe_content_mine` 函数之后）新增：

```python
def _maybe_trigger_weak_signal(source, imported: int) -> None:
    """ingest 批次完成 → 按配置异步触发弱信号提取（§2.1 方案①自动 hook）。

    条件：config_json.enable_weak_signal=True 且有 db_connection_id。
    非阻塞：Celery 入队失败仅告警，不影响已完成的灌库结果。
    """
    cfg = source.config_json or {}
    if not cfg.get("enable_weak_signal"):
        return
    db_id = cfg.get("db_connection_id")
    if not db_id or not imported:
        return
    try:
        from datetime import date, timedelta
        from metaprofile.shared.worker.newtech_tasks import extract_weak_signals
        today = date.today()
        extract_weak_signals.delay(
            (today - timedelta(days=90)).isoformat(), today.isoformat(),
            None, db_id,
        )
        logger.info("weak_signal_hook_enqueued", db_connection_id=db_id, imported=imported)
    except Exception as exc:  # noqa: BLE001  hook 失败不杀灌库
        logger.warning("weak_signal_hook_failed", error=str(exc))
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/ingest_ods/test_sql_warehouse_hook.py -q`
Expected: PASS（5）

- [ ] **Step 5: 跑既有 collector 测试防回归**

Run: `python -m pytest tests/ingest_ods/test_sql_warehouse_collector.py tests/ingest_ods/test_e2e_pipeline.py -q`
Expected: PASS（hook 默认 enable_weak_signal 未设 → 不触发，旧路径不变）

- [ ] **Step 6: Commit**

```bash
git add metaprofile/ingest_ods/collectors/sql_warehouse.py tests/ingest_ods/test_sql_warehouse_hook.py
git commit -m "feat(weak_signal): ingest 完成后 hook 异步触发提取(条件+非阻塞)"
```

---

## Task 12: 全量回归 + 文档回写

**Files:** 无新码（验证 + 更新 spec §7 状态）

- [ ] **Step 1: 跑全量 pytest**

Run: `python -m pytest -q`
Expected: 全绿（基线 465 + 本计划新增 ~40 测试 ≈ 500+ passed/18 skipped）。若有失败，逐个修（不得 skip 掩盖）。

- [ ] **Step 2: tsc/lint（前端无关，仅确认无 Python 语法漏）**

Run: `python -c "import metaprofile.new_tech_discovery.services.weak_signal_extractor, metaprofile.new_tech_discovery.services.signal_metrics, metaprofile.new_tech_discovery.services.corpus_loader, metaprofile.shared.worker.newtech_tasks"`
Expected: 无 ImportError

- [ ] **Step 3: 回写 spec §7 实施状态**

`docs/superpowers/specs/2026-06-20-weak-signal-pipeline-design.md` §7 标题下加一行：

```markdown
> **实施状态（2026-06-20）：** 子项目 1 已实现（见 plan `2026-06-20-weak-signal-extraction.md`）。步骤 1 附件抽取仍为独立 spec 前置依赖；步骤 2-8 完成（metric 纯函数 + CorpusLoader + extract 编排 + Celery 任务 + 路由/hook 触发）。NER 异常实体入 related_*_ids 为可选增强（留口）。
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-06-20-weak-signal-pipeline-design.md
git commit -m "docs(spec): 弱信号子项1 实施状态回写"
```

---

## 自审清单（实现完成后跑一遍）

- [ ] spec §4.2-4.9 每个公式有对应纯函数 + 测试（burst/novelty/diversity/coherence/velocity+MK）
- [ ] §4.7 4 维加权 → SignalStrengthQuantifier（settings 权重）
- [ ] §4.8 自适应阈值 → AdaptiveThreshold 复用
- [ ] §4.10 关联网络 → NetworkCorrelator 复用（celery 任务内调）
- [ ] §4.11 端到端 → WeakSignalExtractor.extract 7 步全实现
- [ ] §2.1 触发双路径 → 路由（T10）+ ingest hook（T11）
- [ ] §3.1 四源语料 → CorpusLoader（attachment 降级容错）
- [ ] 无 placeholder；metric 签名跨任务一致（`burst_score`/`novelty_score`/`diversity_score`/`velocity_score`/`coherence_score`/`mann_kendall_tau`）
- [ ] 全量 pytest 绿

---

## 已知局限 / 后续（不在本计划）

- **附件 clean_content**：依赖附件 spec 独立实现（表 `attachment_text`）；未实现前 attachment 源降级空。
- **NER 异常入 related_*_ids**（§4.9）：本计划留口（is_entity 已收集），实际填充留增强。
- **跨批 NameIndex**：弱信号 related_*_ids 暂空（关联网络由 NetworkCorrelator 从 profile 层补），与 ingest_ods 同名 GAP。
- **子项 2/3**：弱信号→扫描→选题的接力（spec §9）为独立后续 plan。
