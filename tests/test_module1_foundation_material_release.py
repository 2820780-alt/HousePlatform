from app.services.module1_foundation_material_release import releasable_foundation_targets
from app.services.module1_foundation_target_package import targets


def test_release_excludes_unspecified_units_and_group_roles():
    candidates, blocked = releasable_foundation_targets()
    assert len(candidates) + len(blocked) == len(targets()) == 118
    assert len(candidates) == 67
    assert all(item.unit for item in candidates)
    assert all(not item.key.startswith("concrete-") and item.key != "pile-s-06" for item in candidates)
    assert all(reason for _, reason in blocked)
