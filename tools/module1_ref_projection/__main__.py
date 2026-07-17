from __future__ import annotations

import sys

from .cli import main as projection_main
from .runtime_artifacts import main as runtime_artifacts_main


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "build-runtime":
        return runtime_artifacts_main(arguments[1:])
    return projection_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
