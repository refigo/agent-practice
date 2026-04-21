"""Hardcoded restaurant data: menu, reservation availability, in-memory stores."""

from __future__ import annotations

MENU: list[dict] = [
    {
        "name": "비빔밥",
        "category": "메인",
        "price": 12000,
        "ingredients": ["밥", "시금치", "당근", "애호박", "콩나물", "달걀", "고추장"],
        "allergens": ["달걀", "대두"],
        "vegetarian": True,
        "description": "신선한 나물과 고추장이 어우러진 대표 한식.",
    },
    {
        "name": "불고기 덮밥",
        "category": "메인",
        "price": 14000,
        "ingredients": ["밥", "소고기", "양파", "대파", "간장"],
        "allergens": ["소고기", "대두", "밀"],
        "vegetarian": False,
        "description": "달짝지근한 양념 불고기를 얹은 덮밥.",
    },
    {
        "name": "김치찌개",
        "category": "메인",
        "price": 11000,
        "ingredients": ["묵은지", "돼지고기", "두부", "대파"],
        "allergens": ["돼지고기", "대두"],
        "vegetarian": False,
        "description": "깊은 맛의 묵은지로 끓인 얼큰한 찌개.",
    },
    {
        "name": "된장찌개",
        "category": "메인",
        "price": 10000,
        "ingredients": ["된장", "두부", "애호박", "양파", "멸치 육수"],
        "allergens": ["대두", "생선"],
        "vegetarian": False,
        "description": "구수한 된장에 두부와 채소를 넉넉히 넣은 찌개.",
    },
    {
        "name": "해물파전",
        "category": "사이드",
        "price": 15000,
        "ingredients": ["밀가루", "달걀", "쪽파", "오징어", "새우"],
        "allergens": ["밀", "달걀", "갑각류", "오징어"],
        "vegetarian": False,
        "description": "바삭하게 부친 해산물 파전.",
    },
    {
        "name": "두부김치",
        "category": "사이드",
        "price": 9000,
        "ingredients": ["두부", "김치", "돼지고기"],
        "allergens": ["대두", "돼지고기"],
        "vegetarian": False,
        "description": "따뜻한 두부에 볶음 김치를 곁들인 안주.",
    },
    {
        "name": "잡채",
        "category": "사이드",
        "price": 11000,
        "ingredients": ["당면", "시금치", "당근", "양파", "간장"],
        "allergens": ["대두", "밀"],
        "vegetarian": True,
        "description": "채소와 당면을 볶은 명절 음식.",
    },
    {
        "name": "식혜",
        "category": "음료",
        "price": 5000,
        "ingredients": ["쌀", "엿기름", "생강"],
        "allergens": [],
        "vegetarian": True,
        "description": "달콤한 전통 쌀 음료.",
    },
    {
        "name": "수정과",
        "category": "음료",
        "price": 5000,
        "ingredients": ["계피", "생강", "곶감"],
        "allergens": [],
        "vegetarian": True,
        "description": "곶감과 계피향이 어우러진 전통 음료.",
    },
    {
        "name": "호떡",
        "category": "디저트",
        "price": 4000,
        "ingredients": ["밀가루", "흑설탕", "견과류"],
        "allergens": ["밀", "견과류"],
        "vegetarian": True,
        "description": "바삭한 겉면에 달콤한 흑설탕 시럽이 가득.",
    },
]


# 오늘부터 7일간, 점심/저녁 시간대별 남은 자리 수 (4인석 기준)
# 키: "2026-04-22" 형식, 값: { "18:00": 2, "19:00": 0, ... }
RESERVATION_SLOTS: dict[str, dict[str, int]] = {
    "2026-04-22": {"12:00": 3, "13:00": 2, "18:00": 1, "19:00": 0, "20:00": 2},
    "2026-04-23": {"12:00": 4, "13:00": 3, "18:00": 3, "19:00": 2, "20:00": 1},
    "2026-04-24": {"12:00": 2, "13:00": 2, "18:00": 0, "19:00": 0, "20:00": 1},
    "2026-04-25": {"12:00": 4, "13:00": 4, "18:00": 4, "19:00": 3, "20:00": 3},
    "2026-04-26": {"12:00": 1, "13:00": 0, "18:00": 2, "19:00": 1, "20:00": 2},
    "2026-04-27": {"12:00": 3, "13:00": 3, "18:00": 2, "19:00": 2, "20:00": 3},
    "2026-04-28": {"12:00": 4, "13:00": 4, "18:00": 3, "19:00": 2, "20:00": 4},
}


# 런타임 저장소 (세션 단위가 아니라 프로세스 단위 — 데모용).
PLACED_ORDERS: list[dict] = []
RESERVATIONS: list[dict] = []
