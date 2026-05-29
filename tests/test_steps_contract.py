import panel as pn

from qcm.viz import nav


def _viewer(demo_run_path):
    from qcm.viz.app import QCMViewer
    return QCMViewer(str(demo_run_path))


def test_base_overview_anchor_builds(demo_run_path):
    v = _viewer(demo_run_path)
    step = v.shell._steps["review"]
    obj = step.overview_anchor("current")
    assert obj is not None
