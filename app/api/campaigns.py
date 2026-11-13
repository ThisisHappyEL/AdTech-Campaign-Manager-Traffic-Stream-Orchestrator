from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.db.database import get_db
from app.db.models import LocalCampaign, LocalStream, LocalStreamOffer
from app.services.keitaro_client import keitaro_client

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CreateCampaignRequest(BaseModel):
    name: str
    geo: str
    offer_id: int
    group_id: Optional[int] = None


@router.get("/")
def get_campaigns():
    """Получение списка всех кампаний из Keitaro."""
    import asyncio
    return asyncio.run(keitaro_client.get_campaigns(limit=50))


@router.get("/offers")
def get_offers(limit: int = 150):
    """Список офферов из Keitaro для поиска/выбора в выпадающем списке."""
    import asyncio
    offers = asyncio.run(keitaro_client.get_offers(limit=limit))
    return [{"id": o["id"], "name": o["name"]} for o in offers]


@router.post("/create")
def create_campaign(req: CreateCampaignRequest, db: Session = Depends(get_db)):
    """
    Часть 1 ТЗ: Создаватор кампаний.
    Создает кампанию в Keitaro с 2 потоками:
    1. Редирект по GEO на Google.
    2. Редирект на выбранный оффер (100% share).
    """
    import asyncio
    try:
        camp_data = asyncio.run(
            keitaro_client.create_campaign_with_streams(
                name=req.name,
                geo=req.geo,
                offer_id=req.offer_id,
                group_id=req.group_id
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания в Keitaro: {str(e)}")

    # Сохраняем локально
    campaign_id = camp_data["id"]
    local_camp = LocalCampaign(
        id=campaign_id,
        name=req.name,
        group_id=camp_data.get("group_id")
    )
    db.merge(local_camp)
    db.commit()

    return {"status": "success", "campaign": camp_data}