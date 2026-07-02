from decimal import Decimal
from types import SimpleNamespace

from app.models.enums import SourceType
from app.schemas.material_hub_contracts import SourceTrustLevel
from app.services.source_quality_report import (
    build_source_quality_report,
    recommended_next_action,
)


def test_quality_report_counts_products_prices_units_and_review_reasons():
    source = SimpleNamespace(name="ЮгКабель", url="https://yugkabel.ru/", source_type=SourceType.SUPPLIER)
    products = [
        SimpleNamespace(
            raw_name="Кабель ВВГнг 3х2,5",
            raw_category="Кабель",
            raw_brand=None,
            raw_manufacturer=None,
            price=Decimal("120"),
            unit="м",
            availability="в наличии",
            region="Краснодарский край",
        ),
        SimpleNamespace(
            raw_name="Аренда дрели",
            raw_category="Инструмент",
            price=Decimal("500"),
            unit="шт",
            availability="да",
            region="Краснодарский край",
        ),
    ]

    report = build_source_quality_report(
        source=source,
        parameters={"sourceCode": "YUFO_YUGKABEL", "trustLevel": "TEST", "parserStatus": "TEST"},
        products=products,
    )

    assert report.source_code == "YUFO_YUGKABEL"
    assert report.source_name == "ЮгКабель"
    assert report.products_scanned == 2
    assert report.products_parsed == 2
    assert report.prices_detected == 2
    assert report.availability_detected == 2
    assert report.products_ignored == 1
    assert report.common_units == {"м": 1, "шт": 1}
    assert "Кабель" in report.detected_categories
    assert report.trust_level == SourceTrustLevel.TEST
    assert report.recommended_next_action == "keep_preview_only"


def test_quality_report_recommendations_are_actionable():
    assert recommended_next_action(
        parser_problems=["captcha blocked"],
        products_scanned=0,
        products_parsed=0,
        products_need_review=0,
        products_ignored=0,
        detected_categories=[],
        mapped_atom_categories=[],
        common_units={},
        trust_level=SourceTrustLevel.NORMAL,
    ) == "mark_blocked"
    assert recommended_next_action(
        parser_problems=[],
        products_scanned=12,
        products_parsed=12,
        products_need_review=1,
        products_ignored=0,
        detected_categories=["Кабель"],
        mapped_atom_categories=["ELECTRICAL_LIGHTING"],
        common_units={"м": 12},
        trust_level=SourceTrustLevel.NORMAL,
    ) == "enable_create_candidates"
