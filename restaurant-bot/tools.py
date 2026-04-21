"""Function tools that expose hardcoded restaurant data to the agents."""

from __future__ import annotations

import uuid

from agents import function_tool

from data import (
    MENU,
    PLACED_ORDERS,
    RESERVATION_SLOTS,
    RESERVATIONS,
)


# ----------------------------- Menu tools -----------------------------


@function_tool
def get_menu(category: str | None = None, vegetarian_only: bool = False) -> str:
    """Return the menu, optionally filtered by category and/or vegetarian flag.

    Args:
        category: Optional category filter. One of "메인", "사이드", "음료", "디저트".
        vegetarian_only: If True, return only vegetarian items.
    """
    items = MENU
    if category:
        items = [item for item in items if item["category"] == category]
    if vegetarian_only:
        items = [item for item in items if item["vegetarian"]]
    if not items:
        return "조건에 맞는 메뉴가 없습니다."
    lines = [
        f"- {item['name']} ({item['category']}, {item['price']:,}원) — {item['description']}"
        for item in items
    ]
    return "\n".join(lines)


@function_tool
def get_item_details(name: str) -> str:
    """Return ingredients, allergens, and description for a specific menu item.

    Args:
        name: Exact menu item name (e.g., "비빔밥").
    """
    for item in MENU:
        if item["name"] == name:
            allergens = ", ".join(item["allergens"]) if item["allergens"] else "없음"
            return (
                f"{item['name']} ({item['price']:,}원)\n"
                f"설명: {item['description']}\n"
                f"재료: {', '.join(item['ingredients'])}\n"
                f"알레르기 유발 성분: {allergens}\n"
                f"채식 여부: {'예' if item['vegetarian'] else '아니오'}"
            )
    return f"'{name}' 메뉴를 찾을 수 없습니다."


@function_tool
def find_allergen_free_items(allergen: str) -> str:
    """Return menu items that do NOT contain the given allergen.

    Args:
        allergen: Allergen to exclude (e.g., "대두", "밀", "달걀", "갑각류").
    """
    safe = [item for item in MENU if allergen not in item["allergens"]]
    if not safe:
        return f"'{allergen}'이(가) 들어있지 않은 메뉴가 없습니다."
    lines = [f"- {item['name']} ({item['price']:,}원)" for item in safe]
    return f"'{allergen}'을(를) 포함하지 않는 메뉴:\n" + "\n".join(lines)


# ----------------------------- Order tools -----------------------------


@function_tool
def place_order(items: list[str]) -> str:
    """Place an order for one or more menu items and return a confirmation.

    Args:
        items: List of exact menu item names (duplicates allowed for multiple orders).
    """
    if not items:
        return "주문할 메뉴가 비어있습니다."
    menu_by_name = {item["name"]: item for item in MENU}
    unknown = [name for name in items if name not in menu_by_name]
    if unknown:
        return f"다음 메뉴는 존재하지 않습니다: {', '.join(unknown)}"

    total = sum(menu_by_name[name]["price"] for name in items)
    order_id = uuid.uuid4().hex[:6].upper()
    PLACED_ORDERS.append(
        {"order_id": order_id, "items": list(items), "total": total}
    )
    lines = [f"- {name} ({menu_by_name[name]['price']:,}원)" for name in items]
    return (
        f"주문 번호: {order_id}\n"
        f"주문 내역:\n" + "\n".join(lines) + f"\n총 금액: {total:,}원"
    )


# ----------------------------- Reservation tools -----------------------------


@function_tool
def check_availability(date: str, party_size: int) -> str:
    """Check which time slots have availability for the given date and party size.

    Args:
        date: Date string in YYYY-MM-DD format.
        party_size: Number of guests (1–4). Each slot represents a 4-seat table.
    """
    if party_size < 1 or party_size > 4:
        return "1~4인까지만 예약 가능합니다."
    day = RESERVATION_SLOTS.get(date)
    if day is None:
        return f"{date}은(는) 예약 가능한 날짜가 아닙니다. (예약은 2026-04-22 ~ 2026-04-28)"
    available = [time for time, left in day.items() if left > 0]
    if not available:
        return f"{date}에는 남은 자리가 없습니다."
    return f"{date} 예약 가능 시간: {', '.join(available)}"


@function_tool
def make_reservation(
    name: str, date: str, time: str, party_size: int
) -> str:
    """Confirm a reservation if the slot is available.

    Args:
        name: Guest name for the reservation.
        date: Date string in YYYY-MM-DD format.
        time: Time string in HH:MM format (e.g., "19:00").
        party_size: Number of guests (1–4).
    """
    if party_size < 1 or party_size > 4:
        return "1~4인까지만 예약 가능합니다."
    day = RESERVATION_SLOTS.get(date)
    if day is None:
        return f"{date}은(는) 예약 불가 날짜입니다."
    left = day.get(time)
    if left is None:
        return f"{time}은(는) 영업 시간대가 아닙니다. (점심 12:00/13:00, 저녁 18:00~20:00)"
    if left <= 0:
        return f"{date} {time}은 마감되었습니다. 다른 시간을 확인해 주세요."

    day[time] -= 1
    reservation_id = uuid.uuid4().hex[:6].upper()
    RESERVATIONS.append(
        {
            "reservation_id": reservation_id,
            "name": name,
            "date": date,
            "time": time,
            "party_size": party_size,
        }
    )
    return (
        f"예약이 확정되었습니다.\n"
        f"예약 번호: {reservation_id}\n"
        f"예약자: {name}\n"
        f"일시: {date} {time}\n"
        f"인원: {party_size}명"
    )
