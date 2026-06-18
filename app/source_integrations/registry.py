from app.models.source import Source
from app.source_integrations.base import SourceIntegration
from app.source_integrations.lemanapro import LemanaProIntegration


def get_integration(source: Source) -> SourceIntegration | None:
    name = (source.name or "").lower()
    url = (source.url or "").lower()
    if "lemana" in name or "lemanapro" in url or "лемана" in name:
        return LemanaProIntegration(source)
    return None

