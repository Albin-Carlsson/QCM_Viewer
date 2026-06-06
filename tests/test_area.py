import math
from qcm.viz.theme import ELECTRODE_AREA_CM2, area_to_diameter_mm


def test_default_area_is_disc_radius_0_6cm():
    assert ELECTRODE_AREA_CM2 == math.pi * 0.6 ** 2
    assert abs(ELECTRODE_AREA_CM2 - 1.1310) < 1e-3


def test_area_to_diameter_round_trips():
    # radius 0.6 cm -> diameter 1.2 cm = 12 mm
    assert abs(area_to_diameter_mm(math.pi * 0.6 ** 2) - 12.0) < 1e-6
    assert area_to_diameter_mm(0.0) == 0.0
    assert area_to_diameter_mm(None) == 0.0
