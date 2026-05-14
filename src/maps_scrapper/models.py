from dataclasses import dataclass


@dataclass
class Place:
    name: str = ""
    address: str = ""
    website: str = ""
    phone_number: str = ""
    reviews_count: int | None = None
    reviews_average: float | None = None
    store_shopping: str = "No"
    in_store_pickup: str = "No"
    store_delivery: str = "No"
    place_type: str = ""
    opens_at: str = ""
    introduction: str = ""
    latitude: float | None = None
    longitude: float | None = None
