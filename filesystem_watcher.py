"""
filesystem_watcher.py — Silver Tier filesystem monitor

Watches the vault's Needs_Action/ folder using watchdog.
When a new .md file appears, immediately triggers workflow_runner.py.
Also watches vault root for manually dropped DROP_*.md files.

Usage:
    python filesystem_watcher.py                    # default vault: silver_tier
    python filesystem_watcher.py --vault silver_tier
"""

import sys
import time
import argparse
import logging
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("FilesystemWatcher")

PYTHON = sys.executable
COOLDOWN = 5  # seconds — avoid double-triggers on fast file writes


class VaultHandler(FileSystemEventHandler):
    """Handles new .md files dropped into watched folders."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self._last_trigger = 0  # timestamp of last workflow run

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".md":
            return

        # Only act on files inside Needs_Action/ or vault root DROP_ files
        in_needs_action = "Needs_Action" in path.parts
        is_drop = path.parent == self.vault_path and path.name.startswith("DROP_")

        if not (in_needs_action or is_drop):
            return

        # If a DROP_ file was placed in vault root, move it to Needs_Action/
        if is_drop:
            dest = self.vault_path / "Needs_Action" / path.name
            path.rename(dest)
            logger.info(f"Moved {path.name} -> Needs_Action/")
            path = dest

        logger.info(f"New file detected: {path.name} — triggering workflow")
        self._run_workflow()

    def _run_workflow(self):
        """Run workflow_runner.py, debounced by COOLDOWN seconds."""
        now = time.time()
        if now - self._last_trigger < COOLDOWN:
            logger.debug("Cooldown active — skipping duplicate trigger")
            return
        self._last_trigger = now

        try:
            result = subprocess.run(
                [PYTHON, "workflow_runner.py"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            # Print workflow output line by line
            for line in result.stdout.splitlines():
                if line.strip():
                    logger.info(f"[workflow] {line}")
            if result.returncode != 0:
                for line in result.stderr.splitlines():
                    if line.strip():
                        logger.warning(f"[workflow ERR] {line}")
        except Exception as e:
            logger.error(f"Failed to run workflow_runner: {e}")


def main():
    parser = argparse.ArgumentParser(description="Silver Tier — Filesystem Watcher")
    parser.add_argument("--vault", default="silver_tier",
                        help="Path to Obsidian vault (default: silver_tier/)")
    args = parser.parse_args()

    vault = Path(args.vault)
    needs_action = vault / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    handler = VaultHandler(vault_path=vault)
    observer = Observer()

    # Watch Needs_Action/ for new files (recursive=False — flat folder)
    observer.schedule(handler, str(needs_action), recursive=False)
    # Watch vault root for manually dropped DROP_*.md files
    observer.schedule(handler, str(vault), recursive=False)

    observer.start()
    logger.info(f"Watching: {needs_action.resolve()}")
    logger.info(f"Watching: {vault.resolve()} (for DROP_*.md)")
    logger.info("Drop a .md file into Needs_Action/ or a DROP_*.md into vault root to trigger workflow.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Filesystem Watcher stopped.")

    observer.join()


if __name__ == "__main__":
    main()
