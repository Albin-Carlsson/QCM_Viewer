import panel as pn

from qcm.viz import nav


def _classes(obj, found=None):
    """Recursively collect css_classes across the Panel tree."""
    found = found if found is not None else set()
    for c in getattr(obj, "css_classes", None) or []:
        found.add(c)
    for child in getattr(obj, "objects", None) or []:
        _classes(child, found)
    return found


def test_app_builds(demo_run_path):
    from qcm.viz.app import app
    view = app(str(demo_run_path))
    assert view is not None
    assert hasattr(view, "servable")


def test_triad_present_in_every_focus(demo_run_path):
    from qcm.viz.app import QCMViewer
    viewer = QCMViewer(str(demo_run_path))
    for i in range(len(nav.STEPS)):
        viewer.shell.focus.value = i
        classes = _classes(viewer.shell.view())
        for region in ("qcm-anchor", "qcm-selection-bar", "qcm-stats", "qcm-focus-rail"):
            assert region in classes, f"{region} missing in focus {nav.step_id(i)}"


def test_focus_change_keeps_controls_state(demo_run_path):
    from qcm.viz.app import QCMViewer
    viewer = QCMViewer(str(demo_run_path))
    ctrls = viewer.shell.controls
    ctrls.t_range.value = (10.0, 20.0)
    viewer.shell.focus.value = 3  # Quantify
    assert tuple(ctrls.t_range.value) == (10.0, 20.0)
    # Brush target follows the focus.
    assert ctrls.brush_mode.value == nav.brush_target_for_step("quantify")
    viewer.shell.focus.value = 2  # Phases
    assert ctrls.brush_mode.value == nav.brush_target_for_step("phases")


def test_drawer_toggles(demo_run_path):
    from qcm.viz.app import QCMViewer
    viewer = QCMViewer(str(demo_run_path))
    viewer.shell._open_drawer()
    assert viewer.shell.drawer_open.value is True
    viewer.shell._close_drawer()
    assert viewer.shell.drawer_open.value is False
