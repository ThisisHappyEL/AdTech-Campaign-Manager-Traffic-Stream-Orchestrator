from typing import List, Dict, Any

def recalculate_stream_weights(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Пересчитывает веса (share) для списка офферов потока.
    Правила:
    1. Removed офферы получают share = 0.
    2. Pinned офферы сохраняют свой текущий share.
    3. Оставшийся процент (100 - sum(pinned)) делится поровну между unpinned активными офферами.
    4. Сумма весов всех активных офферов всегда равна 100 (или 0, если активных нет).
    """
    active_offers = [o for o in offers if o.get("status") != "removed"]
    
    # Сброс веса у удаленных
    for o in offers:
        if o.get("status") == "removed":
            o["share"] = 0

    if not active_offers:
        return offers

    pinned_offers = [o for o in active_offers if o.get("is_pinned", False)]
    unpinned_offers = [o for o in active_offers if not o.get("is_pinned", False)]

    # Если все активные офферы напинены
    if not unpinned_offers:
        return offers

    # Считаем сумму уже зафиксированных весов
    pinned_total = sum(o.get("share", 0) for o in pinned_offers)
    remaining_share = max(0, 100 - pinned_total)

    num_unpinned = len(unpinned_offers)
    base_share = remaining_share // num_unpinned
    remainder = remaining_share % num_unpinned

    for i, o in enumerate(unpinned_offers):
        # Первые 'remainder' офферов получают +1%, чтобы сумма сошлась ровно в 100%
        o["share"] = base_share + (1 if i < remainder else 0)

    return offers