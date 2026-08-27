from datetime import datetime

import requests

import lunchbot.welplan as welplan_module
from lunchbot.message import format_message
from lunchbot.welplan import (
    cards_to_day_menu,
    course_photos,
    fetch_course_detail,
    is_placeholder_image_bytes,
    merge_live_images,
    parse_lunch_cards,
)

HTML = """
d[186]={id:"20260819-REST000595-E32M-A1",name:"[테이스티가든] 소불고기",date:"20260819",mealTimeId:"2",restaurantId:"REST000595",vendor:"welstory",components:[{name:"[테이스티가든] 소불고기",nutrition:{calories:235}}],nutrition:{calories:1263},isTakeOut:false,hallNo:"E32M",courseType:"A1",imageUrl:"https://img-welmenu.welstory.com/a.jpg"};
d[187]={id:"20260819-REST000595-E32M-AA",name:"[고쌈냉면]_물냉면",date:"20260819",mealTimeId:"2",restaurantId:"REST000595",vendor:"welstory",components:[],nutrition:{calories:916},isTakeOut:false,hallNo:"E32M",courseType:"AA",imageUrl:"https://img-welmenu.welstory.com/b.jpg"};
d[188]={id:"20260819-REST000595-E32M-BB",name:"철판훈제오리볶음밥",date:"20260819",mealTimeId:"2",restaurantId:"REST000595",vendor:"welstory",components:[],nutrition:{calories:790},isTakeOut:false,hallNo:"E32M",courseType:"BB",imageUrl:"https://img-welmenu.welstory.com/c.jpg"};
d[189]={id:"20260819-REST000595-E32M-CC",name:"스키야끼&유자소스",date:"20260819",mealTimeId:"2",restaurantId:"REST000595",vendor:"welstory",components:[],nutrition:{calories:1082},isTakeOut:false,hallNo:"E32M",courseType:"CC",imageUrl:"https://img-welmenu.welstory.com/d.jpg"};
d[190]={id:"20260819-REST000595-E32M-DD",name:"[라면 14종 중 택1]",date:"20260819",mealTimeId:"2",restaurantId:"REST000595",vendor:"welstory",components:[],nutrition:{calories:7195},isTakeOut:false,hallNo:"E32M",courseType:"DD",imageUrl:"https://img-welmenu.welstory.com/e.jpg"};
d[191]={id:"20260819-REST000595-E32M-HH",name:"오징어주꾸미숙회",date:"20260819",mealTimeId:"2",restaurantId:"REST000595",vendor:"welstory",components:[],nutrition:{calories:230},isTakeOut:false,hallNo:"E32M",courseType:"HH",imageUrl:"https://img-welmenu.welstory.com/f.jpg"};
d[192]={id:"20260819-REST000595-E3AB-P5",name:"맛있는새우볶음밥",date:"20260819",mealTimeId:"2",restaurantId:"REST000595",vendor:"welstory",components:[],nutrition:{calories:2371},isTakeOut:false,hallNo:"E3AB",courseType:"P5",imageUrl:"https://img-welmenu.welstory.com/skip.jpg"};
"""


def test_parse_lunch_cards_keeps_main_hall_only() -> None:
    cards = parse_lunch_cards(HTML)
    courses = [card["course_type"] for card in cards]
    assert courses == ["A1", "AA", "BB", "CC", "DD", "HH"]
    assert all(card["hall_no"] == "E32M" for card in cards)


def test_format_matches_legacy_table() -> None:
    cards = parse_lunch_cards(HTML)
    details = {
        "A1": [{"name": "[테이스티가든] 소불고기", "calories": 235}, {"name": "브로컬리", "calories": 25}, {"name": "라이스", "calories": 0}],
        "AA": [{"name": "[고쌈냉면]_물냉면", "calories": 516}, {"name": "숯불불고기", "calories": 0}],
        "BB": [{"name": "철판훈제오리볶음밥", "calories": 553}, {"name": "사골팟국", "calories": 0}],
        "CC": [{"name": "스키야끼&유자소스", "calories": 540}, {"name": "유부양념밥", "calories": 0}],
        "DD": [{"name": "[라면 14종 중 택1]", "calories": 0}, {"name": "신라면", "calories": 0}],
        "HH": [{"name": "오징어주꾸미숙회", "calories": 135}, {"name": "포기김치", "calories": 0}],
    }
    menu = cards_to_day_menu(cards, details, "2026-08-19")
    text = format_message(menu)

    assert text.startswith("### :yum: 오늘의 점심 메뉴 :whatistodaylunch:")
    assert "| **브라운그릴** | **동방식객** | **모던키친** | **별미공방** |" in text
    assert "| **마이보글** | **추가배식대** |" in text
    assert "| **브라운그릴** | **동방식객** |\n" not in text
    assert "![](https://img-welmenu.welstory.com/a.jpg =240x180)" in text
    assert "브로컬리" in text
    assert "<img" not in text
    assert "<br>" not in text
    assert "skip.jpg" not in text
    assert menu.mains[0].station == "브라운그릴"
    assert "1,263kcal" in menu.mains[0].kcal
    assert menu.ramen is not None and menu.ramen.station == "마이보글"


def test_merge_live_images_replaces_recipe_url() -> None:
    cards = parse_lunch_cards(HTML)
    live = [
        {
            "vendor": "welstory",
            "restaurantId": "REST000595",
            "date": "20260819",
            "mealTimeId": "2",
            "id": "20260819-REST000595-E32M-A1",
            "imageUrl": "https://live.example/a.jpg",
        }
    ]
    merged = merge_live_images(cards, live)
    by_course = {card["course_type"]: card for card in merged}
    assert by_course["A1"]["image_url"] == "https://live.example/a.jpg"
    assert by_course["AA"]["image_url"] == "https://img-welmenu.welstory.com/b.jpg"


def test_merge_live_images_ignores_breakfast_photo_of_same_course() -> None:
    """조식 사진이 오늘 새벽에 먼저 올라와도 점심 사진을 밀어내면 안 됩니다."""
    cards = parse_lunch_cards(HTML)
    live = [
        {
            "vendor": "welstory",
            "restaurantId": "REST000595",
            "date": "20260819",
            "mealTimeId": "2",
            "hallNo": "E32M",
            "courseType": "BB",
            "id": "20260819-REST000595-E32M-BB",
            "imageUrl": "https://img-welmenu.welstory.com/s20260812152319.jpg",
        },
        {
            "vendor": "welstory",
            "restaurantId": "REST000595",
            "date": "20260819",
            "mealTimeId": "1",
            "hallNo": "E32M",
            "courseType": "BB",
            "id": "breakfast-bb",
            "imageUrl": "https://img-welmenu.welstory.com/s20260819041017.jpg",
        },
    ]
    merged = merge_live_images(cards, live)
    by_course = {card["course_type"]: card for card in merged}
    assert by_course["BB"]["image_url"] == "https://img-welmenu.welstory.com/s20260812152319.jpg"


def test_placeholder_image_bytes_match_known_hash() -> None:
    assert is_placeholder_image_bytes(b"")
    assert not is_placeholder_image_bytes(b"real-photo")


def test_course_photos_keeps_lunch_only() -> None:
    """조식(1)·석식(3)·야식(4)이 같은 코너코드를 써도 점심만 남아야 합니다."""
    live = [
        {"date": "20260826", "mealTimeId": "1", "hallNo": "E32M", "courseType": "A1",
         "imageUrl": "https://img-welmenu.welstory.com/s20260826041422.jpg"},
        {"date": "20260826", "mealTimeId": "2", "hallNo": "E32M", "courseType": "A1",
         "imageUrl": "https://img-welmenu.welstory.com/s20260821123252.jpg"},
        {"date": "20260826", "mealTimeId": "4", "hallNo": "E32M", "courseType": "AA",
         "imageUrl": "https://img-welmenu.welstory.com/s20260821151723.jpg"},
    ]
    photos = course_photos(live, "20260826")
    assert photos == {"A1": "https://img-welmenu.welstory.com/s20260821123252.jpg"}


def test_course_photos_keeps_rows_without_meal_time() -> None:
    """끼니 필드가 없는 응답까지 버리면 사진이 통째로 사라집니다."""
    live = [
        {"date": "20260826", "hallNo": "E32M", "courseType": "BB",
         "imageUrl": "https://img-welmenu.welstory.com/s20260826110000.jpg"},
    ]
    assert course_photos(live, "20260826") == {
        "BB": "https://img-welmenu.welstory.com/s20260826110000.jpg"
    }


class _Response500:
    """상위 프록시가 nutrient 캐시 미스로 500을 주는 상황."""

    ok = False
    status_code = 500

    def raise_for_status(self):
        raise requests.HTTPError("500 Server Error")

    def json(self):
        return {"error": "Menu nutrient detail cache miss"}


def test_course_detail_500_does_not_raise(monkeypatch) -> None:
    """상세는 부가 정보일 뿐이라, 500이 급식표 전체를 막아선 안 됩니다."""
    monkeypatch.setattr(welplan_module.requests, "get", lambda *a, **k: _Response500())
    assert fetch_course_detail("REST000595", datetime(2026, 8, 27), "E32M", "A1") == []


def test_message_survives_missing_ramen_corner() -> None:
    """DD 카드가 없어도 나머지 코너로 정상 메시지가 나가야 합니다."""
    cards = [card for card in parse_lunch_cards(HTML) if card["course_type"] != "DD"]
    menu = cards_to_day_menu(cards, {}, "2026-08-27")
    text = format_message(menu)
    assert menu.ramen is None
    assert "마이보글" not in text
    assert "추가배식대" in text
    assert "브라운그릴" in text


class _FakePage:
    """Welplan 메뉴 페이지 응답."""

    ok = True
    status_code = 200
    encoding = "utf-8"

    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        pass


class _FakeJson:
    ok = True
    status_code = 200

    def __init__(self, payload) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload


def test_menu_survives_when_detail_api_is_down(monkeypatch) -> None:
    """2026-08-27 장애 재현: DD 카드가 없고 상세 API가 전부 500이어도 급식표는 나가야 합니다."""
    html_no_dd = HTML.replace('courseType:"DD"', 'courseType:"ZZ"')

    def fake_get(url, **kwargs):
        if "/restaurants/" in url:
            return _FakePage(html_no_dd)
        return _Response500()  # 상세·live API 전부 500

    monkeypatch.setattr(welplan_module.requests, "get", fake_get)
    menu = welplan_module.fetch_today_menu()
    assert [item.station for item in menu.mains] == ["브라운그릴", "동방식객", "모던키친", "별미공방"]
    assert menu.ramen is None
    assert menu.extra is not None


def test_ramen_card_built_once_from_detail(monkeypatch) -> None:
    """DD 카드가 없는 날 상세 응답 한 번으로 라면 카드와 반찬 목록을 다 채워야 합니다."""
    html_no_dd = HTML.replace('courseType:"DD"', 'courseType:"ZZ"')
    dd_calls = []

    def fake_get(url, params=None, **kwargs):
        if "/restaurants/" in url:
            return _FakePage(html_no_dd)
        if url.endswith("/menus/detail") and params.get("courseType") == "DD":
            dd_calls.append(url)
            return _FakeJson([
                {"name": "[라면 14종 중 택1]", "nutrition": {"calories": 0}},
                {"name": "신라면", "nutrition": {"calories": 500}},
            ])
        return _Response500()

    monkeypatch.setattr(welplan_module.requests, "get", fake_get)
    menu = welplan_module.fetch_today_menu()
    assert menu.ramen is not None
    assert menu.ramen.name == "[라면 14종 중 택1]"
    assert menu.ramen.items == ["신라면"]
    assert menu.ramen.kcal == "500kcal"
    assert len(dd_calls) == 1  # 같은 상세를 두 번 부르지 않습니다.
