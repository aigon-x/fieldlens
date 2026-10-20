"""Command line interface: inspect / benchmark / serve / synth."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .annotate import annotate
from .benchmark import run_benchmark
from .detect import DEFAULT_PARAMS, Params, inspect_array
from .imageio import ImageDecodeError, encode_png, read_image
from .synth import SynthConfig, generate_dataset

HUMAN_COLUMNS = ("id", "kind", "bbox", "score", "contrast", "elongation")


def _print_human(result, image_path: Path, written: list[Path]) -> None:
    print(f"FieldLens {__version__} — {image_path}")
    print(f"image: {result.image_size[0]}x{result.image_size[1]}  scale={result.scale:.3f}  "
          f"defects={len(result.defects)}  elapsed={result.elapsed_ms:.1f} ms")
    if result.defects:
        header = f"{'id':>3} {'kind':<8} {'bbox':<22} {'score':>6} {'contrast':>9} {'elong':>6}"
        print(header)
        for d in result.defects:
            print(f"{d.id:>3} {d.kind:<8} {str(d.bbox):<22} {d.score:>6.2f} {d.contrast:>9.2f} {d.elongation:>6.2f}")
    else:
        print("no defects above threshold")
    for p in written:
        print(f"wrote: {p}")


def _cmd_inspect(args: argparse.Namespace) -> int:
    image_path = Path(args.image)
    params = DEFAULT_PARAMS
    overrides = {}
    if args.max_dim:
        overrides["max_dim"] = args.max_dim
    if overrides:
        params = Params(**{**params.__dict__, **overrides})
    try:
        img = read_image(image_path)
    except ImageDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = inspect_array(img, params)
    payload = result.to_dict()

    written: list[Path] = []
    if not args.no_write:
        out_dir = Path(args.out_dir) if args.out_dir else Path.cwd() / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = image_path.stem
        json_path = out_dir / f"{stem}.json"
        ann_path = out_dir / f"{stem}_annotated.png"
        mask_path = out_dir / f"{stem}_mask.png"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        ann_path.write_bytes(encode_png(annotate(img, result)))
        if result.mask is not None:
            mask_path.write_bytes(encode_png(result.mask))
        written = [json_path, ann_path, mask_path]

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_human(result, image_path, written)
    return 1 if (args.fail_on_defects and result.defects) else 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    params = DEFAULT_PARAMS
    report = run_benchmark(n=args.n, seed=args.seed, min_f1=args.min_f1, params=params)
    payload = json.dumps(report, indent=2)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(payload, encoding="utf-8")

    if args.json:
        print(payload)
    else:
        print(f"FieldLens {__version__} benchmark — synthetic plates, deterministic seed {args.seed}")
        print(f"images: {report['images']}  clean: {report['clean_images']}  "
              f"time: {report['ms_per_image']:.1f} ms/image ({report['images_per_s']:.1f} img/s)")
        print(f"TP={report['tp']}  FP={report['fp']}  FN={report['fn']}")
        print(f"precision={report['precision']:.4f}  recall={report['recall']:.4f}  f1={report['f1']:.4f}")
        print(f"kind accuracy (matched)={report['kind_accuracy']:.4f}  mean match score={report['mean_match_score']:.4f}")
        for kind, stats in report["per_kind"].items():
            rec = "n/a" if stats["recall"] is None else f"{stats['recall']:.4f}"
            print(f"  {kind:<8} gt={stats['gt']:<3} hit={stats['hit']:<3} pred={stats['pred']:<3} recall={rec}")
        print(f"false positives on clean plates: {report['false_positives_on_clean']} "
              f"({report['fp_per_clean_image']:.2f}/image)")
        gate = "PASS" if report["passed"] else "FAIL"
        print(f"acceptance gate F1 >= {report['min_f1']:.2f}: {gate}")
        if report["failed_images"]:
            print("images with misses (first 10):")
            for f in report["failed_images"]:
                print(f"  seed={f['seed']} gt={f['gt']} det={f['det']} missed={f['missed']}")
    return 0 if report["passed"] else 1


def _cmd_synth(args: argparse.Namespace) -> int:
    cfg = SynthConfig(size=args.size)
    manifest = generate_dataset(args.out, args.n, args.seed, cfg)
    total = sum(len(e["defects"]) for e in manifest["entries"])
    print(json.dumps({"out": str(Path(args.out).resolve()), "images": manifest["count"],
                      "defects": total, "manifest": "ground_truth.json"}, indent=2))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("fieldlens.api:app", host=args.host, port=args.port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fieldlens", description="Classical-CV surface inspection")
    parser.add_argument("--version", action="version", version=f"fieldlens {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ins = sub.add_parser("inspect", help="inspect a single image")
    p_ins.add_argument("image")
    p_ins.add_argument("--out-dir", default=None, help="directory for JSON + annotated PNG (default: ./out)")
    p_ins.add_argument("--no-write", action="store_true", help="do not write artefacts")
    p_ins.add_argument("--json", action="store_true", help="print JSON result to stdout")
    p_ins.add_argument("--max-dim", type=int, default=None, help="working resolution cap")
    p_ins.add_argument("--fail-on-defects", action="store_true", help="exit 1 when any defect is found")
    p_ins.set_defaults(func=_cmd_inspect)

    p_bench = sub.add_parser("benchmark", help="score the detector on a generated dataset")
    p_bench.add_argument("--n", type=int, default=40)
    p_bench.add_argument("--seed", type=int, default=7000)
    p_bench.add_argument("--min-f1", type=float, default=0.80)
    p_bench.add_argument("--json-out", default=None)
    p_bench.add_argument("--json", action="store_true")
    p_bench.set_defaults(func=_cmd_benchmark)

    p_synth = sub.add_parser("synth", help="write a synthetic dataset with ground truth")
    p_synth.add_argument("--out", default="dataset")
    p_synth.add_argument("--n", type=int, default=20)
    p_synth.add_argument("--seed", type=int, default=7000)
    p_synth.add_argument("--size", type=int, default=384)
    p_synth.set_defaults(func=_cmd_synth)

    p_serve = sub.add_parser("serve", help="run the HTTP API")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8099)
    p_serve.set_defaults(func=_cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
