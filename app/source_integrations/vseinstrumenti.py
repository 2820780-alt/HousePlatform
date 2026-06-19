from __future__ import annotations

from app.models.enums import SourceActionType
from app.models.source import Source
from app.source_integrations.base import HealthCheckResult, SourceIntegration, SourceProduct


class VseInstrumentiIntegration(SourceIntegration):
    supported_actions = {
        SourceActionType.CHECK_SOURCE_HEALTH,
        SourceActionType.INITIAL_MATERIAL_SCAN,
        SourceActionType.UPDATE_PRICES,
        SourceActionType.FIND_NEW_PRODUCTS,
    }

    def __init__(self, source: Source):
        self.source = source
        self.base_url = source.url or "https://www.vseinstrumenti.ru/"

    async def check_health(self) -> HealthCheckResult:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(self.base_url, headers=_headers())
            return HealthCheckResult(
                ok=200 <= response.status_code < 400,
                status_code=response.status_code,
                message=(
                    response.reason_phrase
                    if response.status_code != 403
                    else "Access denied by source protection"
                ),
            )
        except Exception as exc:
            return HealthCheckResult(ok=False, message=str(exc))

    async def fetch_products(
        self,
        action_type: SourceActionType,
        parameters: dict | None = None,
    ) -> list[SourceProduct]:
        health = await self.check_health()
        if not health.ok:
            raise RuntimeError(
                f"VseInstrumenti is not available for direct scan: {health.status_code} {health.message}"
            )
        return []


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (compatible; HousePlatformMaterialHub/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
