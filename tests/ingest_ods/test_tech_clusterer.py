from metaprofile.ingest_ods.services.tech_clusterer import normalize_term, cluster_entity_id


def test_normalize_alias_dict():
    assert normalize_term("质谱仪") == normalize_term("质谱")
    assert normalize_term("质谱仪") == normalize_term("mass spectrometry")

def test_normalize_case_punct():
    assert normalize_term("CNN。") == normalize_term("cnn")
    assert normalize_term(" 量子计算 ") == "量子计算"

def test_cluster_entity_id_stable():
    a = cluster_entity_id("质谱仪")
    b = cluster_entity_id("质谱")
    assert a == b
    assert a.startswith("concept:")

def test_cluster_entity_id_diff_for_unrelated():
    assert cluster_entity_id("质谱仪") != cluster_entity_id("量子计算")
