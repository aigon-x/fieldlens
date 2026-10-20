import numpy as np

from fieldlens.quality import assess


def test_flat_plate_is_in_domain():
    plate = np.full((256, 256, 3), 180, dtype=np.uint8)
    assert assess(plate).in_domain


def test_high_frequency_document_is_rejected():
    rng = np.random.default_rng(7)
    texture = rng.integers(0, 255, (256, 256, 3), dtype=np.uint8)
    result = assess(texture)
    assert not result.in_domain
    assert result.code == "outside_domain"
    assert result.message


def test_empty_image_reports_empty():
    result = assess(np.zeros((0, 0, 3), dtype=np.uint8))
    assert not result.in_domain
    assert result.code == "empty"
