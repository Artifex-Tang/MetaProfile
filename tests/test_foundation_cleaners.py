"""
单元测试：foundation/cleaners（纯逻辑，无外部依赖）
"""
from __future__ import annotations

import pytest

from metaprofile.foundation.cleaners.deduplicator import Deduplicator, _normalize_title
from metaprofile.foundation.cleaners.normalizer import normalize
from metaprofile.foundation.cleaners.validator import ValidateOutcome, validate
from metaprofile.foundation.cleaners.pipeline import CleaningPipeline, PipelineStats
from metaprofile.foundation.collectors.base import RawDocument


# ─── 测试工厂 ────────────────────────────────────────────────────────────────

def make_patent(raw_id: str = "CN001", title: str = "量子纠错专利") -> RawDocument:
    return RawDocument(
        source="cnipa",
        doc_type="patent",
        raw_id=raw_id,
        title=title,
        raw_data={
            "ANE": raw_id,
            "TI": title,
            "AB": "一种量子纠错编码方法",
            "AN": "中国科学院",
            "IPC": "G06N 10/70",
            "AD": "2023-01-15",
        },
    )


def make_paper(raw_id: str = "CNKI_001") -> RawDocument:
    return RawDocument(
        source="cnki",
        doc_type="paper",
        raw_id=raw_id,
        title="量子计算综述",
        raw_data={
            "title": "量子计算综述",
            "author": "张三;李四",
            "organ": "清华大学",
            "source": "计算机学报",
            "pubdate": "2023-06",
            "summary": "本文综述量子计算的最新进展。",
            "keyword": "量子计算;量子比特",
        },
    )


def make_project(missing_pj_no: bool = False) -> RawDocument:
    raw: dict = {
        "pjName": "量子纠错关键技术",
        "pi": "王五",
        "orgName": "北京大学",
        "startYear": "2022",
        "endYear": "2025",
    }
    if not missing_pj_no:
        raw["pjNo"] = "62271234"
    return RawDocument(
        source="nsfc",
        doc_type="project",
        raw_id=raw.get("pjNo", ""),
        title=raw.get("pjName"),
        raw_data=raw,
    )


# ─── Deduplicator ───────────────────────────────────────────────────────────

def test_dedup_by_exact_id():
    d = Deduplicator()
    doc = make_patent("CN001")
    unique, dropped = d.dedup([doc, doc])
    assert len(unique) == 1
    assert dropped == 1


def test_dedup_by_title_fingerprint():
    d = Deduplicator()
    doc1 = make_patent("CN001", "量子纠错专利")
    doc2 = make_patent("CN002", "量子纠错专利")  # 不同 ID，同标题
    unique, dropped = d.dedup([doc1, doc2])
    assert len(unique) == 1
    assert dropped == 1


def test_dedup_different_docs_pass_through():
    d = Deduplicator()
    docs = [make_patent(f"CN{i:03d}", f"专利{i}") for i in range(5)]
    unique, dropped = d.dedup(docs)
    assert len(unique) == 5
    assert dropped == 0


def test_dedup_none_title_no_fingerprint_conflict():
    d = Deduplicator()
    doc1 = RawDocument(source="cnipa", doc_type="patent", raw_id="A1", title=None, raw_data={})
    doc2 = RawDocument(source="cnipa", doc_type="patent", raw_id="A2", title=None, raw_data={})
    unique, dropped = d.dedup([doc1, doc2])
    assert len(unique) == 2  # title=None 不参与标题去重


def test_normalize_title_strips_punctuation():
    assert _normalize_title("量子！纠错，方法") == "量子 纠错 方法"


# ─── Normalizer ─────────────────────────────────────────────────────────────

def test_normalize_patent_maps_fields():
    doc = make_patent()
    normed = normalize(doc)
    assert normed.source == "cnipa"
    assert normed.fields.get("title") == "量子纠错专利"
    assert normed.fields.get("application_number") == "CN001"
    assert normed.fields.get("abstract") is not None


def test_normalize_patent_date_parsed():
    doc = make_patent()
    normed = normalize(doc)
    # AD -> application_date 应为 date 对象
    from datetime import date
    assert normed.fields.get("application_date") == date(2023, 1, 15)


def test_normalize_paper_authors_split():
    doc = make_paper()
    normed = normalize(doc)
    authors = normed.fields.get("authors")
    assert isinstance(authors, list)
    assert "张三" in authors
    assert "李四" in authors


def test_normalize_paper_keywords_split():
    doc = make_paper()
    normed = normalize(doc)
    kws = normed.fields.get("keywords")
    assert isinstance(kws, list)
    assert "量子计算" in kws


def test_normalize_preserves_unmapped_fields_with_prefix():
    doc = make_patent()
    normed = normalize(doc)
    # TI 已映射，不应有 raw_TI
    # 未映射字段才有 raw_ 前缀
    assert "raw_TI" not in normed.fields


# ─── Validator ──────────────────────────────────────────────────────────────

def test_validate_patent_pass():
    normed = normalize(make_patent())
    result = validate(normed)
    assert result.outcome == ValidateOutcome.PASS
    assert result.completeness == 1.0


def test_validate_paper_degrade_missing_recommended():
    doc = RawDocument(
        source="cnki",
        doc_type="paper",
        raw_id="X001",
        title="量子计算",
        raw_data={"title": "量子计算"},  # 缺 abstract/authors 等推荐字段
    )
    normed = normalize(doc)
    result = validate(normed)
    assert result.outcome == ValidateOutcome.DEGRADE
    assert 0 < result.completeness < 1.0
    assert len(result.missing_recommended) > 0


def test_validate_project_reject_missing_project_number():
    doc = make_project(missing_pj_no=True)
    normed = normalize(doc)
    result = validate(normed)
    assert result.outcome == ValidateOutcome.REJECT
    assert "project_number" in result.missing_required


def test_validate_completeness_calculation():
    # patent: required=[title, application_number], recommended=[abstract, applicant_name, ipc_codes, application_date]
    # total = 6 fields
    doc = RawDocument(
        source="cnipa",
        doc_type="patent",
        raw_id="CN999",
        title="专利",
        raw_data={"ANE": "CN999", "TI": "专利"},  # 缺 abstract, applicant, ipc, date
    )
    normed = normalize(doc)
    result = validate(normed)
    assert result.outcome == ValidateOutcome.DEGRADE
    assert result.completeness == pytest.approx(2 / 6, rel=0.01)


# ─── Pipeline ───────────────────────────────────────────────────────────────

def test_pipeline_dedup_normalize_validate():
    pipeline = CleaningPipeline()
    raw_docs = [
        make_patent("CN001"),
        make_patent("CN001"),  # 重复
        make_paper("CNKI_001"),
    ]
    cleaned, stats = pipeline.run_sync(raw_docs)
    assert stats.total == 3
    assert stats.deduped == 1
    assert stats.accepted == 2
    assert len(cleaned) == 2


def test_pipeline_rejects_bad_doc():
    pipeline = CleaningPipeline()
    bad = RawDocument(
        source="nsfc",
        doc_type="project",
        raw_id="",
        title=None,
        raw_data={},  # 缺 pjName(title) 和 pjNo → REJECT
    )
    cleaned, stats = pipeline.run_sync([bad])
    assert stats.rejected == 1
    assert len(cleaned) == 0


def test_pipeline_stats_accepted_equals_passed_plus_degraded():
    pipeline = CleaningPipeline()
    docs = [make_patent(f"CN{i:03d}", f"专利{i}") for i in range(3)]
    _, stats = pipeline.run_sync(docs)
    assert stats.accepted == stats.passed + stats.degraded


def test_pipeline_cleaned_doc_has_completeness():
    pipeline = CleaningPipeline()
    cleaned, _ = pipeline.run_sync([make_patent()])
    assert len(cleaned) == 1
    assert 0 < cleaned[0].completeness <= 1.0


@pytest.mark.asyncio
async def test_pipeline_stream():
    pipeline = CleaningPipeline()

    async def raw_stream():
        for i in range(5):
            yield make_patent(f"CN{i:03d}", f"专利{i}")

    batches = []
    async for batch, stats in pipeline.stream(raw_stream(), batch_size=2):
        batches.append((batch, stats))

    total_docs = sum(len(b) for b, _ in batches)
    assert total_docs == 5
    assert len(batches) == 3  # ceil(5/2) = 3
