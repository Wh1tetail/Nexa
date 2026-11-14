"""Delete stored files that no database row refers to.

    python -m scripts.sweep_storage --dry-run      # only list them
    python -m scripts.sweep_storage                # delete them
    python -m scripts.sweep_storage --grace-hours 0

The backend also runs this sweep by itself every STORAGE_SWEEP_INTERVAL_HOURS.
"""
import argparse
from datetime import timedelta

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.storage_cleanup import sweep_orphans


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="only list the orphan files")
    parser.add_argument("--grace-hours", type=float, default=settings.STORAGE_SWEEP_GRACE_HOURS,
                        help="ignore files newer than this (default: %(default)s)")
    args = parser.parse_args()
    with SessionLocal() as db:
        res = sweep_orphans(db, grace=timedelta(hours=args.grace_hours), dry_run=args.dry_run)
    if res.skipped:
        print("Another process is sweeping right now; try again later.")
        return
    for key in res.orphans:
        print(("would delete " if args.dry_run else "deleted ") + key)
    print(f"checked {res.checked} file(s), orphans: {len(res.orphans)}, deleted: {res.deleted}")


if __name__ == "__main__":
    main()
