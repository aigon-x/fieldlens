"""Synthetic generator: determinism, ground-truth sanity, dataset round-trip."""

from __future__ import annotations

import json

import numpy as np

from fieldlens.synth import SynthConfig, generate_dataset, load_dataset, make_sample


def test_same_seed_is_byte_identical() -> None:
    a = make_sample(1234)
    b = make_sample(1234)
    assert np.array_equal(a["image"], b["image"])
    assert a["gt"]["defects"] == b["gt"]["defects"]


def test_different_seeds_differ() -> None:
    a = make_sample(1)["image"]
    b = make_sample(2)["image"]
    assert not np.array_equal(a, b)


def test_ground_truth_boxes_are_sane() -> None:
    for seed in (7002, 7003, 7004, 7005, 7013):
        sample = make_sample(seed)
        h, w = sample["image"].shape[:2]
        assert sample["gt"]["defects"], f"seed {seed} expected defects"
        for d in sample["gt"]["defects"]:
            x, y, bw, bh = d["bbox"]
            assert d["type"] in ("scratch", "dent", "stain")
            assert 0 <= x < w and 0 <= y < h
            assert bw >= 4 and bh >= 4
            assert x + bw <= w and y + bh <= h
            assert d["area_px"] > 0
            assert d["contrast"] > 0


def test_clean_sample_has_no_defects() -> None:
    gt = make_sample(7000)["gt"]
    assert gt["defects"] == []


def test_dataset_round_trip(tmp_path) -> None:
    manifest = generate_dataset(tmp_path, n=4, seed_base=7100, cfg=SynthConfig(size=192))
    assert manifest["count"] == 4
    on_disk = json.loads((tmp_path / "ground_truth.json").read_text(encoding="utf-8"))
    assert len(on_disk["entries"]) == 4
    assert (tmp_path / "images").is_dir()

    loaded = load_dataset(tmp_path)
    assert len(loaded) == 4
    for entry, sample in zip(on_disk["entries"], loaded):
        assert sample["gt"]["defects"] == entry["defects"]
        assert sample["image"].shape[:2] == (192, 192)
        assert sample["image"].dtype == np.uint8
