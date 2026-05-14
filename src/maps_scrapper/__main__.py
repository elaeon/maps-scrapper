import argparse
import logging

from .scraper import scrape_places

_MAX_RESULTS = 100


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [float(x) for x in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be lat_min,lng_min,lat_max,lng_max")
    return parts[0], parts[1], parts[2], parts[3]


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="maps-scrap")
    parser.add_argument("-s", "--search", required=True, help="Search query for Google Maps")
    parser.add_argument(
        "-t",
        "--max-results",
        type=int,
        default=_MAX_RESULTS,
        help=f"Max results to collect (default {_MAX_RESULTS})",
    )
    parser.add_argument("-o", "--output", help="Output file path (.csv or .jsonl)", required=True)
    parser.add_argument(
        "-c",
        "--concat",
        action="store_true",
        help="Concat to the output file instead of overwriting",
    )
    parser.add_argument(
        "--bbox",
        type=_parse_bbox,
        default=None,
        help="Bounding box lat_min,lng_min,lat_max,lng_max",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "jsonl"),
        default=None,
        help="Override output format (default: inferred from extension)",
    )
    args = parser.parse_args()

    _setup_logging()
    total_saved = scrape_places(
        args.search,
        args.max_results,
        args.output,
        concat=args.concat,
        bbox=args.bbox,
        format=args.format,
    )
    logging.info(f"Done. Total saved: {total_saved}")


if __name__ == "__main__":
    main()
