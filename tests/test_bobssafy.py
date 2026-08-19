from lunchbot.bobssafy import STATION_ORDER, is_welmenu_image_url, map_welmenu_images
from lunchbot.models import DayMenu, StationMenu

WELMENU = "https://img-welmenu.welstory.com"


def test_is_welmenu_image_url() -> None:
    assert is_welmenu_image_url(f"{WELMENU}/a.jpg")
    assert not is_welmenu_image_url("https://example.com/a.jpg")
    assert not is_welmenu_image_url("")


def test_map_welmenu_images_assigns_stations_in_order() -> None:
    urls = [f"{WELMENU}/{name}.jpg" for name in "abcdef"]
    photos = map_welmenu_images(urls)

    assert list(photos.keys()) == list(STATION_ORDER)
    assert photos["브라운그릴"] == urls[0]
    assert photos["마이보글"] == urls[5]


def test_map_welmenu_images_ignores_non_welmenu_urls() -> None:
    urls = ["https://example.com/icon.png", f"{WELMENU}/a.jpg"]
    assert map_welmenu_images(urls) == {"브라운그릴": urls[1]}


def test_fill_photos_only_fills_missing() -> None:
    menu = DayMenu(
        date_label="2026-08-19",
        mains=[
            StationMenu(station="브라운그릴", name="a", image_url=""),
            StationMenu(station="동방식객", name="b", image_url="https://existing.example/x.jpg"),
        ],
    )
    menu.fill_photos(
        {"브라운그릴": f"{WELMENU}/new.jpg", "동방식객": f"{WELMENU}/skip.jpg"},
        needs_photo=lambda item: not item.image_url,
    )

    assert menu.mains[0].image_url == f"{WELMENU}/new.jpg"
    assert menu.mains[1].image_url == "https://existing.example/x.jpg"
