import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.db.database import get_db
from app.db.models import LocalCampaign, LocalStream, LocalStreamOffer
from app.services.keitaro_client import keitaro_client
from app.services.weight_calc import recalculate_stream_weights

router = APIRouter(prefix="/api/streams", tags=["streams"])


class AddOfferRequest(BaseModel):
    offer_id: int
    offer_name: Optional[str] = None


class OfferActionRequest(BaseModel):
    offer_id: int


def _serialize_stream(stream: LocalStream) -> Dict[str, Any]:
    return {
        "id": stream.id,
        "campaign_id": stream.campaign_id,
        "name": stream.name,
        "type": stream.type,
        "schema": stream.schema,
        "is_dirty": stream.is_dirty,
        "offers": [
            {
                "id": o.id,
                "offer_id": o.offer_id,
                "offer_name": o.offer_name or f"Offer #{o.offer_id}",
                "share": o.share,
                "is_pinned": o.is_pinned,
                "status": o.status,
            }
            for o in stream.offers
        ],
    }


@router.post("/campaign/{campaign_id}/fetch")
def fetch_campaign_streams(campaign_id: int, db: Session = Depends(get_db)):
    """
    Кнопка 'Fetch streams':
    Тянет потоки из Keitaro, сохраняет в локальную БД.
    Если оффер был удален в самом Keitaro, помечает его как 'removed' (серый).
    """
    try:
        kt_streams = asyncio.run(keitaro_client.get_campaign_streams(campaign_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Keitaro API: {str(e)}")

    # Убеждаемся, что кампания есть в БД
    local_camp = db.query(LocalCampaign).filter_by(id=campaign_id).first()
    if not local_camp:
        local_camp = LocalCampaign(id=campaign_id, name=f"Campaign #{campaign_id}")
        db.add(local_camp)
        db.commit()

    synced_streams = []

    for s_data in kt_streams:
        s_id = s_data["id"]
        stream = db.query(LocalStream).filter_by(id=s_id).first()
        if not stream:
            stream = LocalStream(
                id=s_id,
                campaign_id=campaign_id,
                name=s_data["name"],
                type=s_data.get("type", "regular"),
                schema=s_data.get("schema", "landings"),
                is_dirty=False
            )
            db.add(stream)
            db.flush()
        else:
            stream.name = s_data["name"]
            stream.is_dirty = False

        # Офферы из Keitaro
        kt_offers = s_data.get("offers", [])
        kt_offer_ids = {o["offer_id"] for o in kt_offers}

        # Существующие локальные офферы
        existing_offers = {o.offer_id: o for o in stream.offers}

        # 1. Обновляем или добавляем офферы из Keitaro
        for kt_o in kt_offers:
            oid = kt_o["offer_id"]
            share = kt_o.get("share", 0)
            if oid in existing_offers:
                existing_offers[oid].share = share
                existing_offers[oid].status = "active"
            else:
                new_offer = LocalStreamOffer(
                    stream_id=s_id,
                    offer_id=oid,
                    share=share,
                    is_pinned=False,
                    status="active"
                )
                db.add(new_offer)

        # 2. Если оффер был в нашей базе, но исчез из Keitaro -> помечаем 'removed' (серый архив)
        for oid, local_o in existing_offers.items():
            if oid not in kt_offer_ids:
                local_o.status = "removed"
                local_o.share = 0

        db.commit()
        synced_streams.append(_serialize_stream(stream))

    return {"status": "success", "streams": synced_streams}


@router.post("/{stream_id}/add_offer")
def add_offer(stream_id: int, req: AddOfferRequest, db: Session = Depends(get_db)):
    """Добавление оффера в поток (локальный драфт). Поток становится желтым."""
    stream = db.query(LocalStream).filter_by(id=stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Поток не найден")

    # Проверяем, есть ли уже такой оффер
    existing = db.query(LocalStreamOffer).filter_by(stream_id=stream_id, offer_id=req.offer_id).first()
    if existing:
        existing.status = "active"
        if req.offer_name:
            existing.offer_name = req.offer_name
    else:
        new_offer = LocalStreamOffer(
            stream_id=stream_id,
            offer_id=req.offer_id,
            offer_name=req.offer_name,
            status="active",
            is_pinned=False,
            share=0
        )
        db.add(new_offer)

    stream.is_dirty = True
    db.flush()

    # Пересчет весов
    offers_dicts = [
        {"offer_id": o.offer_id, "share": o.share, "is_pinned": o.is_pinned, "status": o.status}
        for o in stream.offers
    ]
    recalculated = recalculate_stream_weights(offers_dicts)

    for o in stream.offers:
        for r in recalculated:
            if o.offer_id == r["offer_id"]:
                o.share = r["share"]

    db.commit()
    return _serialize_stream(stream)


@router.post("/{stream_id}/remove_offer")
def remove_offer(stream_id: int, req: OfferActionRequest, db: Session = Depends(get_db)):
    """Удаление оффера (оффер сереет, вес 0%, поток желтеет)."""
    stream = db.query(LocalStream).filter_by(id=stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Поток не найден")

    offer = db.query(LocalStreamOffer).filter_by(stream_id=stream_id, offer_id=req.offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Оффер не найден")

    offer.status = "removed"
    offer.share = 0
    offer.is_pinned = False
    stream.is_dirty = True
    db.flush()

    # Пересчет весов остальных
    offers_dicts = [
        {"offer_id": o.offer_id, "share": o.share, "is_pinned": o.is_pinned, "status": o.status}
        for o in stream.offers
    ]
    recalculated = recalculate_stream_weights(offers_dicts)

    for o in stream.offers:
        for r in recalculated:
            if o.offer_id == r["offer_id"]:
                o.share = r["share"]

    db.commit()
    return _serialize_stream(stream)


@router.post("/{stream_id}/bring_back_offer")
def bring_back_offer(stream_id: int, req: OfferActionRequest, db: Session = Depends(get_db)):
    """Возврат удаленного оффера из архива (Bring back)."""
    stream = db.query(LocalStream).filter_by(id=stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Поток не найден")

    offer = db.query(LocalStreamOffer).filter_by(stream_id=stream_id, offer_id=req.offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Оффер не найден")

    offer.status = "active"
    stream.is_dirty = True
    db.flush()

    offers_dicts = [
        {"offer_id": o.offer_id, "share": o.share, "is_pinned": o.is_pinned, "status": o.status}
        for o in stream.offers
    ]
    recalculated = recalculate_stream_weights(offers_dicts)

    for o in stream.offers:
        for r in recalculated:
            if o.offer_id == r["offer_id"]:
                o.share = r["share"]

    db.commit()
    return _serialize_stream(stream)


@router.post("/{stream_id}/toggle_pin")
def toggle_pin(stream_id: int, req: OfferActionRequest, db: Session = Depends(get_db)):
    """Фиксация веса (Pin/Unpin)."""
    stream = db.query(LocalStream).filter_by(id=stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Поток не найден")

    offer = db.query(LocalStreamOffer).filter_by(stream_id=stream_id, offer_id=req.offer_id).first()
    if not offer or offer.status == "removed":
        raise HTTPException(status_code=400, detail="Нельзя напинить удаленный оффер")

    offer.is_pinned = not offer.is_pinned
    db.commit()
    return _serialize_stream(stream)


@router.post("/{stream_id}/cancel")
def cancel_changes(stream_id: int, db: Session = Depends(get_db)):
    """Кнопка Cancel: полный сброс локального черновика к состоянию из Keitaro."""
    stream = db.query(LocalStream).filter_by(id=stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Поток не найден")

    # Удаляем все локальные офферы этого потока, чтобы начисто подтянуть эталон из Keitaro
    db.query(LocalStreamOffer).filter_by(stream_id=stream_id).delete()
    db.commit()

    return fetch_campaign_streams(stream.campaign_id, db)


@router.post("/{stream_id}/push_to_kt")
def push_to_kt(stream_id: int, db: Session = Depends(get_db)):
    """Кнопка Push to KT: отправка итоговых весов в Keitaro API."""
    stream = db.query(LocalStream).filter_by(id=stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Поток не найден")

    active_offers = [
        {"offer_id": o.offer_id, "share": o.share, "status": o.status}
        for o in stream.offers
    ]

    try:
        asyncio.run(keitaro_client.update_stream_offers(stream_id, active_offers))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отправки в Keitaro: {str(e)}")

    stream.is_dirty = False
    db.commit()
    return _serialize_stream(stream)