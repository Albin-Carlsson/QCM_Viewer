import panel as pn

from qcm.viz import nav


def _viewer(demo_run_path):
    from qcm.viz.app import QCMViewer
    return QCMViewer(str(demo_run_path))


def test_data_anchor_builds(demo_run_path):
    v = _viewer(demo_run_path)
    obj = v.shell._data_plot.overview_anchor("current")
    assert obj is not None


def test_three_pages_build(demo_run_path):
    """The three-page redesign exposes a buildable surface per mode."""
    v = _viewer(demo_run_path)
    pages = {
        "data": v.shell._page_data,
        "results": v.shell._page_results,
        "report": v.shell._page_report,
    }
    for name, page in pages.items():
        assert isinstance(page, pn.viewable.Viewable), f"{name} page not viewable"

    # The step objects that feed those pages each render their main surface.
    assert v.shell._results.page() is not None
    assert v.shell._report.page() is not None
    assert isinstance(v.shell._report.secondary_panel(), pn.viewable.Viewable)
