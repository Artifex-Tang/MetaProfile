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
