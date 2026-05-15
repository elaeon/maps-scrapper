import logging
import os

import httpx

from .models import Place

log = logging.getLogger(__name__)

# Override with OVERPASS_URL env var to use an alternative mirror
# e.g. https://overpass.kumi.systems/api/interpreter
OVERPASS_URL = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
_TIMEOUT = 90  # seconds — Overpass can be slow for large areas

# Common OSM tag filters — pass value directly to -s/--search
COMMON_TAGS: dict[str, str] = {
    # Food & drink
    "restaurant": "amenity=restaurant",
    "cafe": "amenity=cafe",
    "bar": "amenity=bar",
    "pub": "amenity=pub",
    "fast_food": "amenity=fast_food",
    "food_court": "amenity=food_court",
    "ice_cream": "amenity=ice_cream",
    # Accommodation
    "hotel": "tourism=hotel",
    "hostel": "tourism=hostel",
    "motel": "tourism=motel",
    "guest_house": "tourism=guest_house",
    # Health
    "hospital": "amenity=hospital",
    "clinic": "amenity=clinic",
    "pharmacy": "amenity=pharmacy",
    "dentist": "amenity=dentist",
    "doctors": "amenity=doctors",
    # Education
    "school": "amenity=school",
    "university": "amenity=university",
    "kindergarten": "amenity=kindergarten",
    # Finance
    "bank": "amenity=bank",
    "atm": "amenity=atm",
    # Transport
    "fuel": "amenity=fuel",
    "parking": "amenity=parking",
    "bus_station": "amenity=bus_station",
    # Shops
    "supermarket": "shop=supermarket",
    "convenience": "shop=convenience",
    "bakery": "shop=bakery",
    "clothes": "shop=clothes",
    "electronics": "shop=electronics",
    "hardware": "shop=hardware",
    # Tourism & leisure
    "museum": "tourism=museum",
    "attraction": "tourism=attraction",
    "viewpoint": "tourism=viewpoint",
    "zoo": "tourism=zoo",
    "park": "leisure=park",
    "playground": "leisure=playground",
    "sports_centre": "leisure=sports_centre",
    "gym": "leisure=fitness_centre",
    # Public services
    "police": "amenity=police",
    "fire_station": "amenity=fire_station",
    "post_office": "amenity=post_office",
    "library": "amenity=library",
    "townhall": "amenity=townhall",
    # Infrastructure
    "toll_booth": "barrier=toll_booth",
}

_TYPE_KEYS = ("amenity", "shop", "tourism", "leisure", "office", "craft", "healthcare", "barrier")


def _tag_to_filter(tag_filter: str) -> str:
    tag_filter = tag_filter.strip()
    return tag_filter if tag_filter.startswith("[") else f"[{tag_filter}]"


def _build_query(
    tag_filter: str,
    area: str | None,
    bbox: tuple[float, float, float, float] | None,
) -> str:
    tag = _tag_to_filter(tag_filter)
    if area:
        return (
            f"[out:json][timeout:{_TIMEOUT}];"
            f'area["name"="{area}"]->.a;'
            f"(node{tag}(area.a);way{tag}(area.a);relation{tag}(area.a););"
            f"out center;"
        )
    lat_min, lng_min, lat_max, lng_max = bbox  # type: ignore[misc]
    bb = f"{lat_min},{lng_min},{lat_max},{lng_max}"
    return (
        f"[out:json][timeout:{_TIMEOUT}];"
        f"(node{tag}({bb});way{tag}({bb});relation{tag}({bb}););"
        f"out center;"
    )


def _element_to_place(elem: dict) -> Place:
    tags = elem.get("tags", {})
    lat = elem["center"]["lat"] if "center" in elem else elem.get("lat")
    lng = elem["center"]["lon"] if "center" in elem else elem.get("lon")

    addr_parts = [
        f"{tags.get('addr:housenumber', '')} {tags.get('addr:street', '')}".strip(),
        tags.get("addr:city", ""),
        tags.get("addr:postcode", ""),
    ]
    address = ", ".join(p for p in addr_parts if p)

    return Place(
        name=tags.get("name", ""),
        address=address,
        website=tags.get("website") or tags.get("contact:website", ""),
        phone_number=tags.get("phone") or tags.get("contact:phone", ""),
        place_type=next((tags[k] for k in _TYPE_KEYS if k in tags), ""),
        introduction=tags.get("description", ""),
        opens_at=tags.get("opening_hours", ""),
        latitude=float(lat) if lat is not None else None,
        longitude=float(lng) if lng is not None else None,
    )


def search_osm(
    tag_filter: str,
    *,
    area: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    total: int | None = None,
) -> list[Place]:
    """Query Overpass API and return Place objects.

    tag_filter: raw OSM tag syntax, e.g. 'amenity=restaurant'
    area: named area for Overpass area lookup, e.g. 'Mexico City'
    bbox: (lat_min, lng_min, lat_max, lng_max)
    total: truncate results to this many places; None means all
    """
    if not area and not bbox:
        raise ValueError("one of area or bbox is required")

    query = _build_query(tag_filter, area, bbox)
    log.info("Querying Overpass API for: %s", tag_filter)

    try:
        resp = httpx.post(
            OVERPASS_URL,
            content=query.encode(),
            timeout=_TIMEOUT + 10,
        )
        resp.raise_for_status()
    except httpx.TimeoutException:
        raise RuntimeError(f"Overpass API timed out after {_TIMEOUT}s") from None
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Overpass API HTTP {e.response.status_code}: {e.response.text[:300]}"
        ) from e

    data = resp.json()
    if "remark" in data:
        log.warning("Overpass remark: %s", data["remark"])

    elements = data.get("elements", [])
    log.info("Overpass returned %d elements", len(elements))

    places = [_element_to_place(e) for e in elements if e.get("tags", {}).get("name")]
    if total is not None:
        places = places[:total]

    log.info("Mapped %d named places", len(places))
    return places
