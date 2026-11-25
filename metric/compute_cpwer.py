#!/usr/bin/env python3
"""cpWER (meeteval) for one dataset.

  --ref_dir : contains stm/<audio_id>.stm
  --hyp_dir : contains stm/<audio_id>.stm

Prints: 16.076% (sub 5.078% / del 5.429% / ins 5.569%)
With --json prints a json object instead.
"""
import argparse
import glob
import json
import os
import warnings

warnings.filterwarnings('ignore')


def stm_text(stm_dir):
    parts = []
    for p in sorted(glob.glob(os.path.join(stm_dir, '*.stm'))):
        with open(p, encoding='utf-8') as f:
            parts.append(f.read())
    return ''.join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ref_dir', required=True)
    ap.add_argument('--hyp_dir', required=True)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    from meeteval.io import STM
    from meeteval.wer import cpwer, combine_error_rates

    ref = STM.parse(stm_text(os.path.join(args.ref_dir, 'stm')))
    hyp = STM.parse(stm_text(os.path.join(args.hyp_dir, 'stm')))
    rates = cpwer(ref, hyp)
    agg = combine_error_rates(*rates.values())

    length = float(agg.length) or 1.0
    res = dict(sessions=len(rates), length=float(agg.length),
               cpwer=float(agg.errors) / length * 100,
               sub=float(agg.substitutions) / length * 100,
               del_=float(agg.deletions) / length * 100,
               ins=float(agg.insertions) / length * 100,
               errors=float(agg.errors),
               sub_n=float(agg.substitutions), del_n=float(agg.deletions),
               ins_n=float(agg.insertions))
    if args.json:
        print(json.dumps(res))
    else:
        print(f"{res['cpwer']:.3f}% (sub {res['sub']:.3f}% / "
              f"del {res['del_']:.3f}% / ins {res['ins']:.3f}%)")


if __name__ == '__main__':
    main()
