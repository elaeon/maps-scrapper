import argparse
import logging
import sys

from .osm import COMMON_TAGS, search_osm
from .scraper import scrape_places
from .writers import append_records, infer_format

MAX_RESULTS: int = 100


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [float(x) for x in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be lat_min,lng_min,lat_max,lng_max")
    return parts[0], parts[1], parts[2], parts[3]


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )


def _print_tags() -> None:
    print("Common OSM tag filters (pass the value to -s/--search):")
    print()
    for name, tag in COMMON_TAGS.items():
        print(f"  {name:<20} {tag}")


def _add_shared_output_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "-o", "--output", help="Output file path (.csv or .jsonl); omit to stream JSONL to stdout"
    )
    p.add_argument(
        "-c", "--concat", action="store_true", help="Append to output file instead of overwriting"
    )
    p.add_argument(
        "--format",
        choices=("csv", "jsonl"),
        default=None,
        help="Override output format (default: inferred from file extension)",
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="maps-scrap")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="{google,osm}")

    # --- google subcommand ---
    gp = subparsers.add_parser(
        "google", help="Scrape places from Google Maps (Playwright/headless)"
    )
    gp.add_argument("-s", "--search", required=True, help="Search query for Google Maps")
    gp.add_argument(
        "-t",
        "--max-results",
        type=int,
        default=MAX_RESULTS,
        help=f"Max results to collect (default {MAX_RESULTS})",
    )
    gp.add_argument(
        "--bbox",
        type=_parse_bbox,
        default=None,
        help="Bounding box lat_min,lng_min,lat_max,lng_max",
    )
    _add_shared_output_args(gp)

    # --- osm subcommand ---
    op = subparsers.add_parser("osm", help="Query OpenStreetMap via Overpass API")
    op.add_argument(
        "-s", "--search", help="OSM tag filter, e.g. 'amenity=restaurant' (see --list-tags)"
    )
    op.add_argument("--area", help="Named area to search in, e.g. 'Mexico City'")
    op.add_argument(
        "--bbox",
        type=_parse_bbox,
        default=None,
        help="Bounding box lat_min,lng_min,lat_max,lng_max",
    )
    op.add_argument(
        "-t",
        "--max-results",
        type=int,
        default=None,
        help="Truncate to this many places (default: return all)",
    )
    op.add_argument(
        "--list-tags", action="store_true", help="Print common OSM tag reference and exit"
    )
    _add_shared_output_args(op)

    args = parser.parse_args()
    _setup_logging()

    if args.command == "google":
        total_saved = scrape_places(
            args.search,
            args.max_results,
            args.output,
            concat=args.concat,
            bbox=args.bbox,
            format=args.format,
        )
        logging.info("Done. Total saved: %d", total_saved)

    elif args.command == "osm":
        if args.list_tags:
            _print_tags()
            return
        if not args.search:
            op.error("-s/--search is required (use --list-tags to see common filters)")
        if not args.area and not args.bbox:
            op.error("one of --area or --bbox is required")

        places = search_osm(
            args.search,
            area=args.area,
            bbox=args.bbox,
            total=args.max_results,
        )
        fmt = args.format or (infer_format(args.output) if args.output else "jsonl")
        saved = append_records(args.output, places, format=fmt, append=args.concat)
        logging.info("Done. Total saved: %d", saved)


if __name__ == "__main__":
    main()
