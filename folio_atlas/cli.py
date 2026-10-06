"""Unified commands; backup and cleanup are always explicit operations."""
import sys
from . import organizer


def main(argv=None):
    organizer.configure_output()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv in (["--help"], ["-h"]):
        print("Folio Atlas — a map of your work\n\n"
              "Commands: learn, preview, apply, verify, refresh, index, undo, backup\n"
              "Use COMMAND --help for arguments. Every sort move stays inside --target.\n"
              "Refresh makes a preview; apply its reviewed plan to move files.\n"
              "Backup and local cleanup are explicit, separate operations.")
        return 0
    if argv and argv[0] == "backup":
        from . import backup
        return backup.main(argv[1:])
    if argv and argv[0] == "refresh":
        argv[0] = "preview"
    return organizer.main(argv)
