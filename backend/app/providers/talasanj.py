import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..models import Quote
from .base import Provider, ProviderError
from .mapping import normalize

MAPPING_PATH = Path(__file__).resolve().parents[2] / "config" / "talasanj_mapping.json"


class TalasanjProvider(Provider):
    name = "Talasanj"
    realtime = False  # flip only after the provider's docs confirm real-time data

    def __init__(self, api_key: str, base_url: str, min_interval_s: float,
                 timeout_s: float, retries: int, backup_api_key: str = "",
                 mapping_path: Path = MAPPING_PATH):
        super().__init__(min_interval_s)
        self.api_key = api_key
        self.backup_api_key = backup_api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.retries = retries
        self.mapping_path = mapping_path
        self.missing_assets: list[str] = []

    def _load_mapping(self) -> dict | None:
        if not self.mapping_path.exists():
            return None
        mapping = json.loads(self.mapping_path.read_text(encoding="utf-8"))
        return mapping if mapping.get("assets") else None

    async def fetch_raw(self):
        """Fetch with backup key only if primary authentication is rejected."""
        keys = list(dict.fromkeys(
            key for key in (self.api_key, self.backup_api_key) if key
        ))
        if not keys:
            raise ProviderError("No Talasanj API key configured")

        last = None
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for key_index, key in enumerate(keys):
                headers = {"Authorization": f"Bearer {key}"}
                auth_rejected = False

                for attempt in range(self.retries + 1):
                    try:
                        r = await client.get(
                            f"{self.base_url}/prices", headers=headers
                        )
                        if r.status_code in (401, 403):
                            auth_rejected = True
                            break
                        if r.status_code == 429:
                            raise ProviderError(
                                "provider rate limit hit (HTTP 429)"
                            )
                        r.raise_for_status()
                        return r.json()
                    except ProviderError:
                        raise
                    except (httpx.HTTPError, ValueError) as e:
                        last = e
                        if attempt < self.retries:
                            await asyncio.sleep(0.5 * (2 ** attempt))

                if auth_rejected and key_index + 1 < len(keys):
                    continue
                if auth_rejected:
                    raise ProviderError(
                        "all configured Talasanj keys rejected authentication"
                    )
                break

        raise ProviderError(
            f"request failed after retries: {type(last).__name__ if last else 'unknown error'}"
        )

    async def _fetch(self) -> list[Quote]:
        mapping = self._load_mapping()
        if mapping is None:
            self.health.status = "unmapped"
            raise ProviderError(
                "no mapping configured: add config/talasanj_mapping.json from a real response")
        raw = await self.fetch_raw()
        quotes, self.missing_assets = normalize(
            raw, mapping, self.name, datetime.now(timezone.utc))
        if not quotes:
            raise ProviderError("response contained none of the mapped assets")
        return quotes
