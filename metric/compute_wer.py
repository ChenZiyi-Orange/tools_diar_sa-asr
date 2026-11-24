#!/usr/bin/env python3
"""Corpus WER for one dataset.

  --ref_dir : contains wer_ref/<audio_id>.txt
  --hyp_dir : contains wer_hyp/<audio_id>.txt

Prints: 12.581% (sub 5.413% / del 3.658% / ins 3.510%)
With --json prints a json object instead.
"""
import argparse
import glob
import json
import os

from rapidfuzz.distance import Levenshtein


def read_tokens(path):
    with open(path, encoding='utf-8') as f:
        return f.read().split()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ref_dir', required=True)
    ap.add_argument('--hyp_dir', required=True)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    refs = {os.path.splitext(os.path.basename(p))[0]: p
            for p in glob.glob(os.path.join(args.ref_dir, 'wer_ref', '*.txt'))}
    hyps = {os.path.splitext(os.path.basename(p))[0]: p
            for p in glob.glob(os.path.join(args.hyp_dir, 'wer_hyp', '*.txt'))}
    ids = sorted(set(refs) & set(hyps))

    n = sub = dele = ins = 0
    for aid in ids:
        ref, hyp = read_tokens(refs[aid]), read_tokens(hyps[aid])
        for op in Levenshtein.opcodes(ref, hyp):
            src_len = op.src_end - op.src_start
            if op.tag == 'replace':
                n += src_len
                sub += src_len
            elif op.tag == 'delete':
                n += src_len
                dele += src_len
            elif op.tag == 'equal':
                n += src_len
            elif op.tag == 'insert':
                ins += op.dest_end - op.dest_start

    n_ = n or 1
    res = dict(utts=len(ids), n=n,
               wer=(sub + dele + ins) / n_ * 100,
               sub=sub / n_ * 100, del_=dele / n_ * 100, ins=ins / n_ * 100)
    if args.json:
        print(json.dumps(res))
    else:
        print(f"{res['wer']:.3f}% (sub {res['sub']:.3f}% / "
              f"del {res['del_']:.3f}% / ins {res['ins']:.3f}%)")


if __name__ == '__main__':
    main()
