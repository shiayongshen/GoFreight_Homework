from __future__ import annotations

import argparse
import json
import sys

from dc_nl_cli.config import load_settings
from dc_nl_cli.errors import DCNLError
from dc_nl_cli.pipeline import build_pipeline


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Data Commons using natural language."
    )
    parser.add_argument("query", help="Natural-language query to execute.")
    parser.add_argument(
        "--resolver-mode",
        choices=["api", "hybrid", "hardrule"],
        default="api",
        help="Resolver strategy for place/stat var mapping.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    settings = load_settings()
    settings = type(settings)(
        **{**settings.__dict__, "resolver_mode": args.resolver_mode}
    )
    pipeline = build_pipeline(settings)
    try:
        output = pipeline.run(args.query)
    except DCNLError as exc:
        print(
            json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
