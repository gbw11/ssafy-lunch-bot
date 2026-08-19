from lunchbot.fetch_menu import (
    BOB_STATION_ORDER,
    apply_bobssafy_photos,
    is_welmenu_image_url,
    map_welmenu_images,
)
from lunchbot.parse_menu import DayMenu, StationMenu


def test_is_welmenu_image_url() -> None:
    assert is_welmenu_image_url("https://img-welmenu.welstory.com/a.jpg")
    assert not is_welmenu_image_url("https://example.com/a.jpg")
    assert not is_welmenu_image_url("")


def test_map_welmenu_images_assigns_stations_in_order() -> None:
    urls = [
        "https://img-welmenu.welstory.com/a.jpg",
        "https://img-welmenu.welstory.com/b.jpg",
        "https://img-welmenu.welstory.com/c.jpg",
        "https://img-welmenu.welstory.com/d.jpg",
        "https://img-welmenu.welstory.com/e.jpg",
        "https://img-welmenu.welstory.com/f.jpg",
    ]
    photos = map_welmenu_images(urls)
    assert list(photos.keys()) == list(BOB_STATION_ORDER)
    assert photos["브라운그릴"] == urls[0]
    assert photos["마이보글"] == urls[5]


def test_map_welmenu_images_ignores_non_welmenu_urls() -> None:
    urls = [
        "https://example.com/icon.png",
        "https://img-welmenu.welstory.com/a.jpg",
    ]
    photos = map_welmenu_images(urls)
    assert photos == {"브라운그릴": urls[1]}


def test_apply_bobssafy_photos_only_fills_missing() -> None:
    menu = DayMenu(
        date_label="2026-08-19",
        mains=[
            StationMenu(station="브라운그릴", name="a", image_url=""),
            StationMenu(station="동방식객", name="b", image_url="https://existing.example/x.jpg"),
        ],
    )
    apply_bobssafy_photos(
        menu,
        {"브라운그릴": "https://img-welmenu.welstory.com/new.jpg", "동방식객": "https://img-welmenu.welstory.com/skip.jpg"},
        needs_photo=lambda item: not item.image_url,
    )
    assert menu.mains[0].image_url == "https://img-welmenu.welstory.com/new.jpg"
    assert menu.mains[1].image_url == "https://existing.example/x.jpg"
