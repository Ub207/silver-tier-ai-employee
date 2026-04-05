import time
import logging
from abc import ABC, abstractmethod
from pathlib import Path


class BaseWatcher(ABC):
    def __init__(self, vault_path: str, check_interval: int = 300):
        self.vault_path = Path(vault_path)
        self.check_interval = check_interval
        self.needs_action = self.vault_path / 'Needs_Action'
        self.needs_action.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def check_for_updates(self):
        """Return a list of new items to process."""
        pass

    @abstractmethod
    def create_action_file(self, item):
        """Create a markdown action file in needs_action/ for the given item."""
        pass

    def run(self):
        self.logger.info(
            f"Starting {self.__class__.__name__} (interval: {self.check_interval}s)"
        )
        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)
            except Exception as e:
                self.logger.error(f"Error during update check: {e}")
            time.sleep(self.check_interval)
