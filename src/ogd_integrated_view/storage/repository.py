from pathlib import Path

import pandas as pd

DEFAULT_DATA_PATH = Path("data/ogd_integrated.xlsx")


class Repository:
    def __init__(self, path: Path = DEFAULT_DATA_PATH):
        self.path = path

    def save(self, source: str, records: list[dict], *, replace: bool = False) -> None:
        if not records:
            return

        sheets = self._read_all_sheets()
        new_df = pd.DataFrame(records)
        existing = None if replace else sheets.get(source)
        sheets[source] = pd.concat([existing, new_df], ignore_index=True) if existing is not None else new_df

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(self.path, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    def load(self, source: str | None = None) -> pd.DataFrame:
        sheets = self._read_all_sheets()
        if source is not None:
            return sheets.get(source, pd.DataFrame())
        if not sheets:
            return pd.DataFrame()
        return pd.concat(sheets.values(), ignore_index=True, sort=False)

    def _read_all_sheets(self) -> dict[str, pd.DataFrame]:
        if not self.path.exists():
            return {}
        return pd.read_excel(self.path, sheet_name=None, engine="openpyxl")
