import re

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from .models import Place

NAME_XP = '//div[@class="TIHn2 "]//h1[@class="DUwDvf lfPIob"]'
ADDRESS_XP = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
WEBSITE_XP = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
PHONE_XP = (
    '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
)
# Combined span: inner_text like "4.3(226)" — present when the place has reviews
REVIEWS_SPAN_XP = '//span[@class="ZkP5Je"]'
# Fallback for average only — shown even for places with no reviews yet
REVIEWS_AVG_FALLBACK_XP = '//div[@class="F7nice "]//span[@aria-hidden="true"]'
PLACE_TYPE_XP = '//div[@class="LBgpqf"]//button[@class="DkEaL "]'
INTRO_XP = '//div[@class="WeS02d fontBodyMedium"]//div[@class="PYvSYb "]'
INFO_ROWS_XP = '//div[@class="LTs0Rc"]'
OPENS_AT_XPATHS = (
    '//button[contains(@data-item-id, "oh")]//div[contains(@class, "fontBodyMedium")]',
    '//div[@class="MkV9"]//span[@class="ZDu9vd"]//span[2]',
)

SERVICE_FLAGS = {
    "shop": "store_shopping",
    "pickup": "in_store_pickup",
    "delivery": "store_delivery",
}

_COORDS_PRIMARY_RE = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")
_COORDS_FALLBACK_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")


def _text(page: Page, xpath: str, timeout_ms: int = 1000) -> str:
    try:
        return page.locator(xpath).first.inner_text(timeout=timeout_ms)
    except PlaywrightError:
        return ""


_REVIEWS_RE = re.compile(r"([\d.,]+)\(([\d,\xa0]+)\)")


def _parse_reviews(page: Page) -> tuple[float | None, int | None]:
    """Return (average, count) from the combined reviews span, with avg-only fallback."""
    raw = _text(page, REVIEWS_SPAN_XP)
    if raw:
        m = _REVIEWS_RE.search(raw)
        if m:
            avg = float(m.group(1).replace(",", "."))
            count = int(m.group(2).replace(",", "").replace("\xa0", ""))
            return avg, count
    # Fallback: avg only, no count (new or review-less places)
    avg_raw = _text(page, REVIEWS_AVG_FALLBACK_XP)
    if avg_raw:
        try:
            return float(avg_raw.replace(",", ".")), None
        except ValueError:
            pass
    return None, None


def _parse_opens_at(page: Page) -> str:
    for xp in OPENS_AT_XPATHS:
        raw = _text(page, xp)
        if not raw:
            continue
        parts = raw.split("⋅")
        text = parts[1] if len(parts) > 1 else raw
        return text.replace(" ", "").strip()
    return ""


def _parse_coords(url: str) -> tuple[float | None, float | None]:
    match = _COORDS_PRIMARY_RE.search(url) or _COORDS_FALLBACK_RE.search(url)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def _service_flags(page: Page) -> dict[str, str]:
    flags: dict[str, str] = {}
    for row in page.locator(INFO_ROWS_XP).all_text_contents():
        parts = row.split("·")
        if len(parts) < 2:
            continue
        marker = parts[1].replace("\n", "").lower()
        for keyword, attr in SERVICE_FLAGS.items():
            if keyword in marker:
                flags[attr] = "Yes"
    return flags


def extract_place(page: Page) -> Place:
    lat, lng = _parse_coords(page.url)
    avg, count = _parse_reviews(page)
    place = Place(
        name=_text(page, NAME_XP),
        address=_text(page, ADDRESS_XP),
        website=_text(page, WEBSITE_XP),
        phone_number=_text(page, PHONE_XP),
        place_type=_text(page, PLACE_TYPE_XP),
        introduction=_text(page, INTRO_XP) or "None Found",
        reviews_average=avg,
        reviews_count=count,
        opens_at=_parse_opens_at(page),
        latitude=lat,
        longitude=lng,
    )
    for attr, value in _service_flags(page).items():
        setattr(place, attr, value)
    return place
