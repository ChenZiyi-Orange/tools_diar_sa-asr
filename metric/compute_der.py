#!/usr/bin/env python3
"""DER (pyannote) for one dataset, one line per collar.

  --ref_dir : contains rttm/<audio_id>.rttm
  --hyp_dir : contains rttm/<audio_id>.rttm

DiarizationErrorRate(collar=..., skip_overlap=False), accumulated over files.

Prints one line per collar (default: 0.0 and 0.25):
  collar=0.0 7.347% (miss 2.806% / fa 1.775% / conf 2.767%)
  collar=0.25 5.123% (miss 1.900% / fa 1.200% / conf 2.023%)
With --json prints a list of json objects instead.
"""
import argparse
import glob
import json
import os
import warnings

warnings.filterwarnings('ignore')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ref_dir', required=True)
    ap.add_argument('--hyp_dir', required=True)
    ap.add_argument('--collars', nargs='*', type=float, default=[0.0, 0.25])
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    from pyannote.core import Annotation
    from pyannote.database.util import load_rttm
    from pyannote.metrics.diarization import DiarizationErrorRate

    def load_ann(path, uri):
        d = load_rttm(path)
        if uri in d:
            return d[uri]
        return next(iter(d.values())) if d else Annotation(uri=uri)

    refs = {os.path.splitext(os.path.basename(p))[0]: p
            for p in glob.glob(os.path.join(args.ref_dir, 'rttm', '*.rttm'))}
    hyps = {os.path.splitext(os.path.basename(p))[0]: p
            for p in glob.glob(os.path.join(args.hyp_dir, 'rttm', '*.rttm'))}
    ids = sorted(set(refs) & set(hyps))

    out = []
    for collar in args.collars:
        metric = DiarizationErrorRate(collar=collar, skip_overlap=False)
        for aid in ids:
            metric(load_ann(refs[aid], aid), load_ann(hyps[aid], aid))
        c = dict(metric[:])
        total = float(c['total']) or 1.0
        miss, fa, conf = (float(c['missed detection']), float(c['false alarm']),
                          float(c['confusion']))
        out.append(dict(collar=collar,
                        der=(miss + fa + conf) / total * 100,
                        miss=miss / total * 100, fa=fa / total * 100,
                        conf=conf / total * 100,
                        total_s=total, miss_s=miss, fa_s=fa, conf_s=conf))

    if args.json:
        print(json.dumps(out))
    else:
        for r in out:
            print(f"collar={r['collar']} {r['der']:.3f}% "
                  f"(miss {r['miss']:.3f}% / fa {r['fa']:.3f}% / "
                  f"conf {r['conf']:.3f}%)")


if __name__ == '__main__':
    main()
