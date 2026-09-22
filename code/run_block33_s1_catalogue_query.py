"""Deprecated historical name; use s1_duck_selection.py (native Block35).

Only legacy --probe/--search aliases remain. Broad 2016-present and RESTO
equivalence are NOT silently reproduced; interval/budget live in CONFIG.json.
No TOPS temporal route is scientifically selected/excluded by this wrapper.
"""
import sys
from s1_duck_selection import main as stable_main


def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    if args==['--probe']:args=['probe']
    elif args==['--search']:args=['catalogue']
    return stable_main(args)


if __name__=='__main__':raise SystemExit(main())
