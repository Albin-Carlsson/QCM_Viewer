import panel as pn


def test_viewer_builds_against_demo_run(demo_run_path):
    from qcm.viz.app import app

    view = app(str(demo_run_path))
    assert view is not None
    # The root is a Panel object that can be served.
    assert hasattr(view, "servable")


def test_each_step_renders(demo_run_path):
    from qcm.viz.app import QCMViewer
    from qcm.viz import nav

    viewer = QCMViewer(str(demo_run_path))
    for i in range(len(nav.STEPS)):
        viewer.shell.step.value = i
        rendered = viewer.shell._steps[nav.step_id(i)].view()
        assert isinstance(rendered, pn.Column)
