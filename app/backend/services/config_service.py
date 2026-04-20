import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"


class ConfigService:
    @staticmethod
    def get_config_path(filename: str) -> Path:
        return CONFIG_DIR / filename

    @staticmethod
    def load_json(filename: str) -> dict[str, Any]:
        path = ConfigService.get_config_path(filename)

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def save_json(filename: str, data: dict[str, Any]) -> None:
        path = ConfigService.get_config_path(filename)

        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)