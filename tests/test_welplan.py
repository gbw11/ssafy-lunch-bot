from lunchbot.format_message import format_mattermost_message
from lunchbot.welplan import (
    cards_to_day_menu,
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
    text = format_mattermost_message(menu)

    assert text.startswith("### :yum: 오늘의 점심 메뉴 :whatistodaylunch:")
    assert "| **브라운그릴** | **동방식객** | **모던키친** | **별미공방** |" in text
    assert "| **마이보글** | **추가배식대** |" in text
    assert "| **브라운그릴** | **동방식객** |\n" not in text
    assert "![](https://img-welmenu.welstory.com/a.jpg)" in text
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


def test_merge_live_images_prefers_today_photo_across_meal_times() -> None:
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
    assert by_course["BB"]["image_url"] == "https://img-welmenu.welstory.com/s20260819041017.jpg"


def test_placeholder_image_bytes_match_known_hash() -> None:
    assert is_placeholder_image_bytes(b"")
    assert not is_placeholder_image_bytes(b"real-photo")
