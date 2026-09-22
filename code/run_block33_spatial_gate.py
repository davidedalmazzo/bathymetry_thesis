"""Deprecated historical wrapper: offline evidence comparison, no hard gates.

Use s1_spatial_compare.py --phase frf-a/frf-b/frf-refined. No independent ASCII
parser, wind downloader, fixed incidence/depth/gradient or accuracy floor.
"""
import argparse
from s1_spatial_compare import compare


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=('frf-a','frf-b','frf-refined'),default='frf-a')
    compare(p.parse_args(argv).phase)
    return 0


if __name__=='__main__':raise SystemExit(main())
