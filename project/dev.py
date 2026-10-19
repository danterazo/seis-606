import logging
from typing import Final

from homelab_dashboard.terminal import PINK, log_line
from watchfiles import Change, run_process
from watchfiles.filters import PythonFilter

WATCH_PATHS: Final[tuple[str, ...]] = ("project/homelab_dashboard", "project/server.py", "project/app.py")


def report_changes(changes: set[tuple[Change, str]]) -> None:
    count: int = len(changes)
    label: str = "change" if count == 1 else "changes"
    log_line((f"{count} {label} detected", PINK))


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    run_process(
        *WATCH_PATHS,
        target="python3 project/app.py",
        target_type="command",
        watch_filter=PythonFilter(),
        grace_period=0.5,
        callback=report_changes,
    )


if __name__ == "__main__":
    main()
