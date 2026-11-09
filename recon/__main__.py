"""Command line entry point: python -m recon run --books ... --gstr2b ... --out ..."""
import argparse
import os
from collections import defaultdict

from recon.io import load_gstr2b, load_purchase_register
from recon.matcher import reconcile
from recon.report import export_report
from recon.rules import decide, load_config

# default config lives next to the package, so the CLI works from any directory
DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "config", "itc_rules.yaml")


def run(args):
    books = load_purchase_register(args.books)
    gstr2b = load_gstr2b(args.gstr2b)
    results = reconcile(books, gstr2b)
    config = load_config(args.config)
    entries = [{**result, **decide(result, config)} for result in results]
    export_report(entries, books, gstr2b, args.out)

    counts = defaultdict(int)
    for entry in entries:
        counts[entry["category"]] += 1
    for category, count in sorted(counts.items()):
        print(f"{category}: {count}")
    print(f"Report written to {args.out}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="recon",
        description="Reconcile a purchase register against GSTR-2B and export an ITC report.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="reconcile and export the Excel report")
    run_parser.add_argument("--books", required=True, help="purchase register CSV")
    run_parser.add_argument("--gstr2b", required=True, help="GSTR-2B CSV")
    run_parser.add_argument("--out", required=True, help="output .xlsx path")
    run_parser.add_argument("--config", default=DEFAULT_CONFIG, help="rules YAML")
    args = parser.parse_args(argv)
    if args.command == "run":
        run(args)


if __name__ == "__main__":
    main()
