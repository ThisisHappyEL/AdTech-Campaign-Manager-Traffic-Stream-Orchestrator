import re
import uuid
import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings


class KeitaroClient:
    def __init__(self):
        self.base_url = settings.KEITARO_BASE_URL
        self.headers = {
            "Api-Key": settings.KEITARO_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{self.base_url}{endpoint}"
            response = await client.request(method, url, headers=self.headers, **kwargs)
            if response.status_code >= 400:
                raise RuntimeError(f"Keitaro API {response.status_code}: {response.text}")
            return response.json()

    async def get_offers(self, limit: int = 200) -> List[Dict[str, Any]]:
        return await self._request("GET", f"/offers?limit={limit}")

    async def get_campaigns(self, limit: int = 100) -> List[Dict[str, Any]]:
        return await self._request("GET", f"/campaigns?limit={limit}")

    async def get_campaign_streams(self, campaign_id: int) -> List[Dict[str, Any]]:
        return await self._request("GET", f"/campaigns/{campaign_id}/streams")

    async def _resolve_campaign_defaults(self) -> Dict[str, Any]:
        """
        Динамически подтягивает домен, группу и источник трафика по API.
        Если в тестовом аккаунте списки пустые — использует безопасный фолбэк.
        """
        group_id = settings.DEFAULT_GROUP_ID
        domain_id = settings.DEFAULT_DOMAIN_ID
        traffic_source_id = settings.DEFAULT_TRAFFIC_SOURCE_ID

        try:
            groups = await self._request("GET", "/groups?type=campaigns")
            if groups and isinstance(groups, list):
                group_id = groups[0]["id"]
        except Exception:
            pass

        try:
            domains = await self._request("GET", "/domains")
            if domains and isinstance(domains, list):
                domain_id = domains[0]["id"]
        except Exception:
            pass

        try:
            sources = await self._request("GET", "/traffic_sources")
            if sources and isinstance(sources, list):
                traffic_source_id = sources[0]["id"]
        except Exception:
            pass

        return {
            "group_id": group_id,
            "domain_id": domain_id,
            "traffic_source_id": traffic_source_id,
        }

    async def create_campaign_with_streams(
        self,
        name: str,
        geo: str,
        offer_id: int,
        group_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Часть 1 ТЗ: Создание кампании с двумя потоками:
        1. GEO -> Редирект на Google
        2. Целевой поток -> Редирект на выбранный оффер
        """
        defaults = await self._resolve_campaign_defaults()

        # Генерируем уникальный alias (обязательное поле в Keitaro API)
        clean_slug = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-")[:20]
        unique_alias = f"{clean_slug}-{uuid.uuid4().hex[:6]}"

        campaign_payload = {
            "name": name,
            "alias": unique_alias,
            "type": "position",
            "group_id": group_id or defaults["group_id"],
            "traffic_source_id": defaults["traffic_source_id"],
            "cost_type": "CPC",
            "cost_auto": True,
        }
        if defaults["domain_id"] is not None:
            campaign_payload["domain_id"] = defaults["domain_id"]

        campaign = await self._request("POST", "/campaigns", json=campaign_payload)
        campaign_id = campaign["id"]

        # 2. Создаем Поток 1 (Фильтр гео на Google)
        stream_1_payload = {
            "campaign_id": campaign_id,
            "name": f"{geo.upper()} -> Google",
            "type": "regular",
            "position": 1,
            "schema": "redirect",
            "action_type": "http",
            "action_payload": "https://google.com",
            "collect_clicks": True,
            "filters": [
                {
                    "name": "country",
                    "mode": "accept",
                    "payload": [geo.upper()]
                }
            ],
            "offers": []
        }
        await self._request("POST", "/streams", json=stream_1_payload)

        # 3. Создаем Поток 2 (Целевой на оффер со 100% веса)
        stream_2_payload = {
            "campaign_id": campaign_id,
            "name": "Остальные -> оффер",
            "type": "regular",
            "position": 2,
            "schema": "landings",
            "action_type": "http",
            "collect_clicks": True,
            "filters": [],
            "offers": [
                {
                    "offer_id": offer_id,
                    "share": 100,
                    "state": "active"
                }
            ]
        }
        await self._request("POST", "/streams", json=stream_2_payload)

        return campaign

    async def update_stream_offers(self, stream_id: int, offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Отправка измененных офферов в Keitaro (Push to KT).
        """
        active_offers_payload = [
            {
                "offer_id": o["offer_id"],
                "share": int(o["share"]),
                "state": "active"
            }
            for o in offers if o.get("status") != "removed" and o.get("share", 0) > 0
        ]

        payload = {
            "offers": active_offers_payload
        }
        return await self._request("PUT", f"/streams/{stream_id}", json=payload)


keitaro_client = KeitaroClient()