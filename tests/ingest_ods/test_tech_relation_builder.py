from metaprofile.ingest_ods.services.tech_relation_builder import (
    build_containment_triples,
)


def test_l2_with_parent_ipc_links_to_l1():
    trips = build_containment_triples(
        l2_concepts=[
            {"entity_id": "concept:abc", "name": "图像识别", "parent_ipc": "G06T"}
        ],
        l1_subclasses={"G06T"},
    )
    assert len(trips) == 1
    t = trips[0]
    assert t.subject_id == "ipc:G06T"
    assert t.object_id == "concept:abc"
    assert t.relation.value == "包含"


def test_l2_without_parent_ipc_no_edge():
    trips = build_containment_triples(
        l2_concepts=[
            {"entity_id": "concept:xyz", "name": "孤立技术", "parent_ipc": None}
        ],
        l1_subclasses={"G06T"},
    )
    assert trips == []
