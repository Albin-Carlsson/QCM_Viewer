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


def test_pages_render_per_mode(demo_run_path):
    """Each top-level mode mounts its own page with the expected regions."""
    from qcm.viz.app import QCMViewer
    viewer = QCMViewer(str(demo_run_path))
    expected = {
        "data": ("qcm-page-data", "qcm-toolbar2", "qcm-anchor", "qcm-rail", "qcm-stats"),
        "results": ("qcm-page-results",),
        "report": ("qcm-page-report",),
    }
    for i, mode in enumerate(nav.MODES):
        viewer.shell.mode.value = i
        classes = _classes(viewer.shell.view())
        for region in expected[mode.id]:
            assert region in classes, f"{region} missing on page {mode.id}"
        # Pages are mutually exclusive: only the active page is mounted.
        for other in nav.MODES:
            if other.id != mode.id:
                assert f"qcm-page-{other.id}" not in classes, f"{other.id} leaked onto {mode.id}"


def test_mode_change_keeps_controls_state(demo_run_path):
    from qcm.viz.app import QCMViewer
    viewer = QCMViewer(str(demo_run_path))
    ctrls = viewer.shell.controls
    ctrls.t_range.value = (10.0, 20.0)
    viewer.shell.mode.value = nav.mode_index("results")
    assert tuple(ctrls.t_range.value) == (10.0, 20.0)
    viewer.shell.mode.value = nav.mode_index("data")
    assert tuple(ctrls.t_range.value) == (10.0, 20.0)


def test_drawer_toggles(demo_run_path):
    from qcm.viz.app import QCMViewer
    viewer = QCMViewer(str(demo_run_path))
    viewer.shell._open_drawer()
    assert viewer.shell.drawer_open.value is True
    viewer.shell._close_drawer()
    assert viewer.shell.drawer_open.value is False
