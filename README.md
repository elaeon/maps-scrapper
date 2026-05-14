## Overview

This tool collects place data from two sources:

- **Google Maps** (`google` subcommand) — uses Playwright to drive a headless Chromium browser. Supports single searches and large-scale geographic coverage via a grid of map tiles.
- **OpenStreetMap** (`osm` subcommand) — queries the [Overpass API](https://overpass-api.de) directly. No browser required; results are available instantly for any tag filter.

Both sources write to the same output schema (CSV or JSONL), so results can be concatenated with `--concat`.

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Install Playwright browsers *(Google Maps only)*

```bash
uv run playwright install chromium
```

This downloads Chromium to `~/.cache/ms-playwright/`. Only needed once, and only if you use the `google` subcommand.

---

## Google Maps

### Basic usage

```bash
uv run maps-scrap google -s "Restaurants in Ensenada, Baja California" -t 20 -o output.csv
```

Omit `-o` to stream JSONL to stdout (useful for piping to other tools).

### Arguments

| Flag | Description | Default |
|------|-------------|---------|
| `-s` / `--search` | Search query for Google Maps | required |
| `-t` / `--max-results` | Maximum number of results to collect | `100` |
| `-o` / `--output` | Output file (`.csv` or `.jsonl`); omit for stdout JSONL | — |
| `-c` / `--concat` | Append to existing output file instead of overwriting | off |
| `--bbox` | Bounding box: `lat_min,lng_min,lat_max,lng_max` | — |
| `--format` | Force output format (`csv` or `jsonl`) | inferred from `-o` |

### City-wide coverage with `--bbox`

Google Maps caps a single search at ~20–60 results. For full city coverage, pass a bounding box — the scraper divides it into a grid of tiles and searches each one independently.

```bash
uv run maps-scrap google \
  -s "Estacionamiento publico en cdmx" \
  --bbox 19.05,-99.40,19.60,-98.85 \
  -o parking_lot_cdmx.csv
```

#### CDMX bounding box reference

| Corner | Latitude | Longitude |
|--------|----------|-----------|
| South-West | 19.05 | -99.40 |
| North-East | 19.60 | -98.85 |

### How it works

1. **Initial search** — opens Google Maps, runs the query, waits for the results feed. Center coordinates are extracted from the URL.
2. **Tile grid** — without `--bbox`, a square grid is centered on the search location (size estimated from `max_results / 12`). With `--bbox`, tiles cover the full bounding box at `TILE_ZOOM=14`, `TILE_STEP=0.04°` (~4.4 km).
3. **Per-tile scraping** — for each tile, the scraper scrolls the results panel to load all listings, deduplicates against a global seen-set, then navigates to each new place URL to extract data.
4. **Data extraction** — name, address, website, phone, review average/count, place type, opening hours, introduction, store flags, and latitude/longitude (parsed from `!3d{lat}!4d{lng}` in the URL).
5. **Incremental saving** — results are written after every tile, so an interrupted run preserves all data collected so far.

---

## OpenStreetMap (Overpass API)

### Basic usage

```bash
# Search by tag + bounding box
uv run maps-scrap osm -s "amenity=restaurant" --bbox 19.42,-99.15,19.44,-99.13 -o output.csv

# Search by tag + named area
uv run maps-scrap osm -s "shop=supermarket" --area "Mexico City" -t 50 -o output.jsonl

# See built-in tag reference
uv run maps-scrap osm --list-tags
```

### Arguments

| Flag | Description | Default |
|------|-------------|---------|
| `-s` / `--search` | OSM tag filter, e.g. `amenity=restaurant` | required |
| `--area` | Named area to search in, e.g. `"Mexico City"` | — |
| `--bbox` | Bounding box: `lat_min,lng_min,lat_max,lng_max` | — |
| `-t` / `--max-results` | Truncate to this many results (default: return all) | — |
| `-o` / `--output` | Output file (`.csv` or `.jsonl`); omit for stdout JSONL | — |
| `-c` / `--concat` | Append to existing output file instead of overwriting | off |
| `--format` | Force output format (`csv` or `jsonl`) | inferred from `-o` |
| `--list-tags` | Print the built-in OSM tag reference and exit | — |

Either `--area` or `--bbox` is required. Both can be combined to narrow results to an area within a bbox.

### Tag syntax

OSM tag filters follow the Overpass QL syntax: `key=value`. Examples:

```
amenity=restaurant
shop=supermarket
tourism=hotel
barrier=toll_booth
```

Run `maps-scrap osm --list-tags` for a full reference of common categories.

### Overpass API endpoint

By default the tool uses `https://overpass-api.de/api/interpreter`. To use an alternative mirror, set the `OVERPASS_URL` environment variable:

```bash
OVERPASS_URL=https://overpass.kumi.systems/api/interpreter uv run maps-scrap osm ...
```

---

## Output Schema

Both sources produce the same columns. Fields that are unavailable for a given source are left empty.

| Column | Google Maps | OSM | Description |
|--------|:-----------:|:---:|-------------|
| `name` | ✓ | ✓ | Place name |
| `address` | ✓ | ✓ | Street address (`addr:*` tags on OSM) |
| `website` | ✓ | ✓ | Website URL |
| `phone_number` | ✓ | ✓ | Phone number |
| `reviews_count` | ✓ | — | Number of reviews |
| `reviews_average` | ✓ | — | Average star rating |
| `store_shopping` | ✓ | — | In-store shopping available (`Yes`/`No`) |
| `in_store_pickup` | ✓ | — | Pickup available (`Yes`/`No`) |
| `store_delivery` | ✓ | — | Delivery available (`Yes`/`No`) |
| `place_type` | ✓ | ✓ | Category (e.g. `restaurant`, `supermarket`) |
| `opens_at` | ✓ | ✓ | Opening hours summary |
| `introduction` | ✓ | ✓ | Short description |
| `latitude` | ✓ | ✓ | Latitude |
| `longitude` | ✓ | ✓ | Longitude |
