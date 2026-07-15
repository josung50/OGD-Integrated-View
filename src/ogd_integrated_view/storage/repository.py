from pathlib import Path

import pandas as pd

DEFAULT_DATA_PATH = Path("data/ogd_integrated.xlsx")


class Repository:
    def __init__(self, path: Path = DEFAULT_DATA_PATH):
        self.path = path

    def save(self, source: str, records: list[dict]) -> None:
        raise NotImplementedError

    def load(self, source: str | None = None) -> pd.DataFrame:
        raise NotImplementedError
