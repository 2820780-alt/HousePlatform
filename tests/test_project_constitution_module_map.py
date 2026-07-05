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
    assert "'Price Dynamics Legacy Alias', 'Legacy alias', 'legacy', 14, 14, 14, 140, 'MERGED'" in sql


def test_module10_keeps_technical_code_but_exposes_vitrina_project_catalog():
    module_sql = _read("database/migrations/20260625_module03_seed_system_modules.sql")
    widget_sql = _read("database/migrations/20260628_module03_widget_registry.sql")
    doc = _read("docs/Modules/Module_10_Marketplace_v1.0.md")

    assert "'MODULE_10_MARKETPLACE', 'MODULE_10_MARKETPLACE', 'Vitrina'" in module_sql
    assert "'project-catalog','Каталог проектов'" in widget_sql
    assert "'PROJECT_CATALOG'" in widget_sql
    assert "Технический код: `MODULE_10_MARKETPLACE`" in doc
    assert "Витрина" in doc
    assert "`PROJECT_CATALOG`" in doc
    assert "Маркетплейс" not in doc
    assert "Корзина" not in doc


def test_role_matrix_seed_does_not_grant_old_module8_or_tenders():
    sql = _read("database/migrations/20260627_module03_role_access_matrix.sql")

    assert "('SUPER_ADMIN', 'MODULE_09_PROCUREMENT', 'ADMIN', 'GLOBAL')" in sql
    assert "('CUSTOMER', 'MODULE_09_PROCUREMENT', 'VIEW', 'OWN')" in sql
    assert "('SUPER_ADMIN', 'MODULE_08_PROCUREMENT'" not in sql
    assert "('SUPER_ADMIN', 'MODULE_09_TENDERS'" not in sql
    assert "('CUSTOMER', 'MODULE_08_PROCUREMENT'" not in sql


def test_module14_docs_are_legacy_alias_and_module11_owns_price_dynamics():
    module14_doc = _read("docs/Modules/Module_14_PriceDynamics_v1.0.md")
    module11_doc = _read("docs/Modules/Module_11_Analytics_v1.0.md")

    assert "Технический код совместимости: `MODULE_14_PRICE_HISTORY`" in module14_doc
    assert "Канонический модуль: `MODULE_11_ANALYTICS`" in module14_doc
    assert "Статус: `MERGED` / legacy alias." in module14_doc
    assert "не является самостоятельным актуальным модулем" in module14_doc
    assert "Module 11 является каноническим владельцем функции `PRICE_DYNAMICS`" in module11_doc
