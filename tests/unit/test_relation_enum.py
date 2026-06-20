from metaprofile.shared.schemas.relations import RelationType


def test_tech_evolve_exists_and_value():
    assert RelationType.TECH_EVOLVE.value == "演进"


def test_tech_prereq_exists_and_value():
    assert RelationType.TECH_PREREQ.value == "前置"


def test_tech_tech_types_are_distinct():
    assert RelationType.TECH_EVOLVE != RelationType.TECH_PREREQ
