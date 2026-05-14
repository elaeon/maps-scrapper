import logging
import math
import os
import re
from urllib.parse import quote_plus

from playwright.sync_api import Error as PlaywrightError, Page, sync_playwright

from .extractor import NAME_XP, extract_place
from .models import Place
from .writers import append_records, infer_format

TILE_ZOOM = 14
TILE_STEP = 0.04  # ~4.4 km at zoom 14
DEFAULT_CENTER = (19.4326, -99.1332)  # CDMX, fallback when search URL lacks @lat,lng
PLACES_PER_TILE_ESTIMATE = 12
MAX_SCROLL_ITERS = 20

CONSENT_SELECTORS = (
    'button[aria-label="Accept all"]',
    'button[aria-label="Reject all"]',
    'form[action*="consent"] button',
    '//button[contains(text(),"Accept all")]',
    '//button[contains(text(),"I agree")]',
)
PLACE_LINK_XP = '//a[contains(@href, "https://www.google.com/maps/place")]'
SEARCH_INPUT_SEL = 'input[id="searchboxinput"], input[name="q"]'
FEED_SEL = '[role="feed"]'

log = logging.getLogger(__name__)


def dismiss_consent(page: Page) -> None:
    for selector in CONSENT_SELECTORS:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(2000)
                return
        except PlaywrightError:
            continue


def collect_feed_urls(page: Page, want: int) -> list[str]:
    try:
        panel = page.locator(FEED_SEL).first
        panel.wait_for(timeout=10000)
        box = panel.bounding_box()
    except PlaywrightError:
        return []
    if not box:
        return []

    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2
    prev = 0
    for _ in range(MAX_SCROLL_ITERS):
        page.mouse.move(cx, cy)
        page.mouse.wheel(0, 10000)
        page.wait_for_timeout(1500)
        found = page.locator(PLACE_LINK_XP).count()
        log.info(f"Currently found: {found}")
        if found >= want or found == prev:
            break
        prev = found

    links = page.locator(PLACE_LINK_XP).all()[:want]
    return [href for link in links if (href := link.get_attribute("href"))]


def grid_around(center: tuple[float, float], tiles: int) -> list[tuple[float, float]]:
    side = math.ceil(math.sqrt(tiles))
    half = side // 2
    lat0, lng0 = center
    return [
        (lat0 + (i - half) * TILE_STEP, lng0 + (j - half) * TILE_STEP)
        for i in range(side)
        for j in range(side)
    ]


def tiles_in_bbox(bbox: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    lat_min, lng_min, lat_max, lng_max = bbox
    out: list[tuple[float, float]] = []
    lat = lat_min
    while lat <= lat_max + 1e-9:
        lng = lng_min
        while lng <= lng_max + 1e-9:
            out.append((round(lat, 6), round(lng, 6)))
            lng += TILE_STEP
        lat += TILE_STEP
    return out


def _plan_tiles(
    page: Page,
    total: int,
    bbox: tuple[float, float, float, float] | None,
) -> list[tuple[float, float]]:
    if bbox:
        tiles = tiles_in_bbox(bbox)
        log.info(f"Bbox search: {len(tiles)} tiles covering {bbox}")
        return tiles

    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", page.url)
    center = (float(m.group(1)), float(m.group(2))) if m else DEFAULT_CENTER
    log.info(f"Search center: ({center[0]:.4f}, {center[1]:.4f})")

    if total <= 20:
        return [center]
    tiles = grid_around(center, math.ceil(total / PLACES_PER_TILE_ESTIMATE))
    log.info(f"Grid search: {len(tiles)} tiles planned")
    return tiles


def _scrape_tile_places(page: Page, urls: list[str], limit: int) -> list[Place]:
    out: list[Place] = []
    for url in urls:
        if len(out) >= limit:
            break
        try:
            page.goto(url, timeout=30000)
            page.wait_for_selector(NAME_XP, timeout=10000)
            page.wait_for_timeout(1500)
            place = extract_place(page)
        except PlaywrightError as e:
            log.warning(f"Failed to extract {url}: {e}")
            continue
        if place.name:
            out.append(place)
        else:
            log.warning(f"No name found at {url}, skipping")
    return out


def scrape_places(
    search_for: str,
    total: int,
    output_path: str,
    *,
    concat: bool = False,
    bbox: tuple[float, float, float, float] | None = None,
    format: str | None = None,
) -> int:
    """Scrape places and persist them incrementally after each tile. Returns total saved."""
    fmt = format or infer_format(output_path)
    seen_urls: set[str] = set()
    total_saved = 0
    file_initialized = concat and os.path.isfile(output_path)
    query_enc = quote_plus(search_for)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("https://www.google.com/maps", timeout=60000)
            page.wait_for_timeout(3000)
            dismiss_consent(page)

            search_input = page.locator(SEARCH_INPUT_SEL).first
            search_input.wait_for(timeout=30000)
            search_input.fill(search_for)
            page.keyboard.press("Enter")
            page.wait_for_selector(FEED_SEL, timeout=30000)
            page.wait_for_timeout(2000)

            tiles = _plan_tiles(page, total, bbox)

            for tile_idx, (lat, lng) in enumerate(tiles):
                if total_saved >= total:
                    break

                log.info(f"Tile {tile_idx + 1}/{len(tiles)} | saved {total_saved}/{total}")

                if tile_idx > 0:
                    url = f"https://www.google.com/maps/search/{query_enc}/@{lat},{lng},{TILE_ZOOM}z"
                    page.goto(url, timeout=60000)
                    page.wait_for_timeout(2000)
                    try:
                        page.wait_for_selector(FEED_SEL, timeout=15000)
                    except PlaywrightError:
                        log.warning(f"No results feed for tile {tile_idx + 1}, skipping")
                        continue

                urls = collect_feed_urls(page, total - total_saved)
                new_urls = [u for u in urls if u not in seen_urls]
                seen_urls.update(urls)
                log.info(f"  {len(urls)} found in tile, {len(new_urls)} new")

                tile_places = _scrape_tile_places(page, new_urls, total - total_saved)
                if tile_places:
                    append_records(
                        output_path, tile_places, format=fmt, append=file_initialized
                    )
                    file_initialized = True
                    total_saved += len(tile_places)
                    log.info(f"  Saved {len(tile_places)} places (total: {total_saved})")
        finally:
            browser.close()
    return total_saved
