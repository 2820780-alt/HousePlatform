from __future__ import annotations

from app.models.enums import SourceActionType
from app.models.source import Source
from app.source_integrations.base import HealthCheckResult, SourceIntegration, SourceProduct


FIRST_WAVE_BLOCKED_MESSAGE = (
    "VseInstrumenti blocks automatic analysis; excluded from the first wave. "
    "Do not bypass source protection. Use approved feed/file workflow later."
)


class VseInstrumentiIntegration(SourceIntegration):
    supported_actions = {
        SourceActionType.CHECK_SOURCE_HEALTH,
    }
    parser_status = "BLOCKED"
    update_mode = "disabled"
    write_mode = "preview_only"
    trust_level = "BLOCKED"
    notes = FIRST_WAVE_BLOCKED_MESSAGE

    def __init__(self, source: Source):
        self.source = source
        self.base_url = source.url or "https://www.vseinstrumenti.ru/"

    async def check_health(self) -> HealthCheckResult:
        return HealthCheckResult(ok=False, message=FIRST_WAVE_BLOCKED_MESSAGE)

    async def fetch_products(
        self,
        action_type: SourceActionType,
        parameters: dict | None = None,
    ) -> list[SourceProduct]:
        raise RuntimeError(FIRST_WAVE_BLOCKED_MESSAGE)


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (compatible; AtomMaterialHub/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
