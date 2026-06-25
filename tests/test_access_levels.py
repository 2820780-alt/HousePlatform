from app.core.access_levels import (
    ACCESS_LEVELS,
    ACCESS_SCOPES_ARE_NOT_ACCESS_LEVELS,
    AccessLevel,
    is_access_scope,
    is_valid_access_level,
)


def test_access_levels_are_action_levels_only():
    assert ACCESS_LEVELS == (
        "NO_ACCESS",
        "VIEW",
        "CREATE",
        "EDIT",
        "APPROVE",
        "ADMIN",
    )
    assert AccessLevel.APPROVE == "APPROVE"


def test_access_scopes_are_not_access_levels():
    for scope in ACCESS_SCOPES_ARE_NOT_ACCESS_LEVELS:
        assert is_access_scope(scope) is True
        assert is_valid_access_level(scope) is False


def test_valid_access_level_check():
    assert is_valid_access_level("VIEW") is True
    assert is_valid_access_level("VIEW_RELEVANT") is False
