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


def test_every_step_has_anchor_and_secondary(demo_run_path):
    v = _viewer(demo_run_path)
    for sid in ("review", "reference", "phases", "quantify", "report"):
        step = v.shell._steps[sid]
        assert step.anchor_plot() is not None, f"{sid} anchor_plot"
        assert isinstance(step.secondary_panel(), pn.viewable.Viewable), f"{sid} secondary_panel"
