from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_system_module_seed_uses_constitution_module_map():
    sql = _read("database/migrations/20260625_module03_seed_system_modules.sql")

    assert "'MODULE_08_TARIFFS', 'MODULE_08_TARIFFS'" in sql
    assert "'MODULE_08_PARTNER_PORTAL'" not in sql
    assert "'MODULE_08_PROCUREMENT', 'MODULE_09_PROCUREMENT'" in sql
    assert "'MODULE_09_PROCUREMENT', 'MODULE_09_PROCUREMENT'" in sql
    assert "'MODULE_09_TENDERS', 'MODULE_09_PROCUREMENT'" in sql
    assert "'MODULE_10_MARKETPLACE', 'MODULE_10_MARKETPLACE', 'Vitrina'" in sql
    assert "'MODULE_11_ANALYTICS', 'MODULE_11_ANALYTICS'" in sql
    assert "'MODULE_14_PRICE_HISTORY', 'MODULE_11_ANALYTICS'" in sql


def test_role_matrix_seed_does_not_grant_old_module8_or_tenders():
    sql = _read("database/migrations/20260627_module03_role_access_matrix.sql")

    assert "('SUPER_ADMIN', 'MODULE_09_PROCUREMENT', 'ADMIN', 'GLOBAL')" in sql
    assert "('CUSTOMER', 'MODULE_09_PROCUREMENT', 'VIEW', 'OWN')" in sql
    assert "('SUPER_ADMIN', 'MODULE_08_PROCUREMENT'" not in sql
    assert "('SUPER_ADMIN', 'MODULE_09_TENDERS'" not in sql
    assert "('CUSTOMER', 'MODULE_08_PROCUREMENT'" not in sql
