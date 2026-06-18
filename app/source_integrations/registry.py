from app.models.source import Source
from app.source_integrations.base import SourceIntegration
from app.source_integrations.baucenter import BaucenterIntegration
from app.source_integrations.bonolit import BonolitIntegration
from app.source_integrations.lemanapro import LemanaProIntegration


def get_integration(source: Source) -> SourceIntegration | None:
    name = (source.name or "").lower()
    url = (source.url or "").lower()
    if "baucenter" in name or "baucenter" in url or "бауцентр" in name:
        return BaucenterIntegration(source)
    if "lemana" in name or "lemanapro" in url or "лемана" in name:
        return LemanaProIntegration(source)
    if "bonolit" in name or "bonolit" in url or "бонолит" in name:
        return BonolitIntegration(source)
    return None
