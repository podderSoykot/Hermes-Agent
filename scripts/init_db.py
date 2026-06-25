import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hermes.db.session import init_db


def main() -> None:
    init_db()
    print("PostgreSQL schema initialized.")


if __name__ == "__main__":
    main()
