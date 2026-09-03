from justincard.v121_core import MAX_ADD_QUANTITY, normalize_add_quantity


def test_quantity_defaults_and_clamps():
    assert normalize_add_quantity(None) == 1
    assert normalize_add_quantity(0) == 1
    assert normalize_add_quantity("3") == 3
    assert normalize_add_quantity(MAX_ADD_QUANTITY + 100) == MAX_ADD_QUANTITY
