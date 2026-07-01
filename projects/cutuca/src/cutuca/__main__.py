"""CLI entry.

    python -m cutuca run                  # boot listener + scheduler (v0 default)
    python -m cutuca digest               # run one digest and exit (cron / testing)
    python -m cutuca parse "texto..."     # test the parser in isolation (needs key)

Loads .env if python-dotenv is present; otherwise relies on the ambient environment.
"""

from __future__ import annotations

import sys

from .app import DEFAULT_CONFIG_PATH, run, run_digest_once


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv  # optional convenience

        load_dotenv()
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _load_dotenv()
    cmd = argv[0] if argv else "run"

    if cmd == "run":
        run(DEFAULT_CONFIG_PATH)
        return 0
    if cmd == "digest":
        run_digest_once(DEFAULT_CONFIG_PATH)
        return 0
    if cmd == "parse":
        if len(argv) < 2:
            print("usage: python -m cutuca parse \"<mensagem>\"", file=sys.stderr)
            return 2
        from .parser import parse_task

        result = parse_task(argv[1])
        print(result)
        return 0

    print(f"unknown command: {cmd}", file=sys.stderr)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
