"""CLI: artefact writing, JSON output, benchmark gate exit code."""

from __future__ import annotations

import json

import cv2

from fieldlens.cli import main
from fieldlens.imageio import encode_png


def _write_sample(tmp_path, sample, name="plate.png"):
    path = tmp_path / name
    path.write_bytes(encode_png(sample["image"]))
    return path


def test_inspect_writes_json_and_images(tmp_path, scratch_sample, capsys) -> None:
    img_path = _write_sample(tmp_path, scratch_sample)
    out_dir = tmp_path / "out"
    rc = main(["inspect", str(img_path), "--out-dir", str(out_dir), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["defect_count"] >= 1

    written = sorted(p.name for p in out_dir.iterdir())
    assert "plate.json" in written
    assert "plate_annotated.png" in written
    assert "plate_mask.png" in written

    ann = cv2.imread(str(out_dir / "plate_annotated.png"))
    mask = cv2.imread(str(out_dir / "plate_mask.png"), cv2.IMREAD_GRAYSCALE)
    assert ann is not None and ann.shape[:2] == scratch_sample["image"].shape[:2]
    assert mask is not None and mask.shape == scratch_sample["image"].shape[:2]


def test_inspect_missing_file_exits_2(tmp_path, capsys) -> None:
    rc = main(["inspect", str(tmp_path / "nope.png"), "--no-write"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_inspect_fail_on_defects(tmp_path, scratch_sample, clean_samples) -> None:
    bad = _write_sample(tmp_path, scratch_sample, "bad.png")
    good = _write_sample(tmp_path, clean_samples[0], "good.png")
    assert main(["inspect", str(bad), "--no-write", "--fail-on-defects"]) == 1
    assert main(["inspect", str(good), "--no-write", "--fail-on-defects"]) == 0


def test_benchmark_cli_reports_numbers(capsys) -> None:
    rc = main(["benchmark", "--n", "8", "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["images"] == 8
    assert 0.0 <= report["f1"] <= 1.0
    assert report["f1"] >= 0.80


def test_synth_cli_writes_dataset(tmp_path, capsys) -> None:
    rc = main(["synth", "--out", str(tmp_path / "ds"), "--n", "2", "--size", "160"])
    assert rc == 0
    info = json.loads(capsys.readouterr().out)
    assert info["images"] == 2
    assert (tmp_path / "ds" / "ground_truth.json").is_file()
