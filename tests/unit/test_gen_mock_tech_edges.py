from scripts.gen_mock_data import build_dataset


def test_mock_has_evolve_and_prereq_edges():
    ds = build_dataset(n=20, seed=20260615)
    rel_types = {r["relation"] for r in ds.relations}
    # Neo4j 关系类型存枚举名（与现有 mock 一致：ORG_EMPLOY 等）
    assert "TECH_EVOLVE" in rel_types
    assert "TECH_PREREQ" in rel_types


def test_mock_evolve_edges_are_tech_tech():
    ds = build_dataset(n=20, seed=20260615)
    evolve = [r for r in ds.relations if r["relation"] == "TECH_EVOLVE"]
    assert len(evolve) >= 3
    assert all(r["subject_type"] == "TECH" and r["object_type"] == "TECH" for r in evolve)


TECH_EDGE_TYPES = ("TECH_EVOLVE", "TECH_PREREQ")


def test_mock_deterministic_across_runs():
    a = [r for r in build_dataset(20, 20260615).relations if r["relation"] in TECH_EDGE_TYPES]
    b = [r for r in build_dataset(20, 20260615).relations if r["relation"] in TECH_EDGE_TYPES]
    assert a == b
