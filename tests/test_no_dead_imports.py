"""Guards that retired modules and helpers stay gone."""
import importlib

import pytest


def test_pages_and_layout_modules_removed():
    for name in ("qcm.viz.pages", "qcm.viz.layout"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)


def test_design_exposes_only_css():
    from qcm.viz import design

    assert hasattr(design, "APP_CSS")
    for gone in ("section_header", "metric_card", "metric_table", "meta_pill"):
        assert not hasattr(design, gone), f"{gone} should be deleted"
