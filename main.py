import argparse

import build_tracker
import ingest_github
import ingest_places
from region import load_region


def cmd_github(args):
    ingest_github.run(load_region(args.region), args.limit)

def cmd_places(args):
    ingest_places.run(load_region(args.region), args.confirm)

def cmd_build(args):
    build_tracker.run()


def main():
    parser = argparse.ArgumentParser(
        description="Find and rank small local tech companies for outreach.")
    sub = parser.add_subparsers(dest="command", required=True)

    # Shared option, defined once and reused by the subcommands that need it
    region_opt = argparse.ArgumentParser(add_help=False)
    region_opt.add_argument("--region", default="regions/houston.toml",
                            help="path to a region .toml file")

    p = sub.add_parser("github", parents=[region_opt],
                       help="find GitHub orgs in the region")
    p.add_argument("--limit", type=int, default=300,
                   help="max orgs per location")
    p.set_defaults(func=cmd_github)

    p = sub.add_parser("places", parents=[region_opt],
                       help="find companies with Google Places")
    p.add_argument("--confirm", action="store_true",
                   help="actually call the paid API")
    p.set_defaults(func=cmd_places)

    p = sub.add_parser("build", help="merge, score, and write the tracker")
    p.set_defaults(func=cmd_build)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()