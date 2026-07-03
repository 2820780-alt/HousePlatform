from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Sequence

from app.config import settings
from app.database import async_session_factory, init_db
from app.services.module3_demo_seed import (
    build_module3_demo_seed_plan,
    recreate_module3_demo_data,
    reset_module3_demo_data,
    seed_module3_demo_data,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.module3_demo_seed",
        description="Local control for Module №3 demo users without starting the API server.",
    )
    parser.add_argument("command", choices=("plan", "create", "reset", "recreate"))
    parser.add_argument("--environment", default=settings.APP_ENV)
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Explicitly allow demo data mutation in development/demo/staging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="For reset: show what would be removed without deleting records.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


async def run_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "plan":
        return build_module3_demo_seed_plan(args.environment).to_dict()

    await init_db()
    async with async_session_factory() as session:
        try:
            if args.command == "create":
                result = await seed_module3_demo_data(
                    session,
                    environment=args.environment,
                    enabled=args.enable,
                )
                payload = result.to_dict()
            elif args.command == "reset":
                result = await reset_module3_demo_data(
                    session,
                    environment=args.environment,
                    enabled=args.enable,
                    dry_run=args.dry_run,
                )
                payload = result.to_dict()
            else:
                payload = await recreate_module3_demo_data(
                    session,
                    environment=args.environment,
                    enabled=args.enable,
                )

            if args.dry_run:
                await session.rollback()
            else:
                await session.commit()
            return payload
        except Exception:
            await session.rollback()
            raise


def format_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.dry_run and args.command != "reset":
        parser.error("--dry-run is only supported for reset.")
    payload = asyncio.run(run_command(args))
    print(format_payload(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
