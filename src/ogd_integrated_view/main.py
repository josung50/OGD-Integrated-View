from dotenv import load_dotenv

from ogd_integrated_view.collectors.collector import collect_all
from ogd_integrated_view.storage.repository import Repository


def main() -> None:
    load_dotenv()
    repository = Repository()
    collect_all(repository)


if __name__ == "__main__":
    main()
