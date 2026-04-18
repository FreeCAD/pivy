# pyright: reportMissingModuleSource=false

from pivy import coin
from pivy.gui import soqt


def build_scene() -> coin.SoSeparator:
    root = coin.SoSeparator()
    shape: coin.SoNode = coin.SoCone()
    root.addChild(shape)

    child_count: int = root.getNumChildren()
    first_child: coin.SoNode = root.getChild(0)
    if child_count != 1:
        raise AssertionError(first_child)

    direction = coin.SbVec3f(1.0, 2.0, 3.0)
    length: float = direction.normalize()
    color = coin.SbColor(0.2, 0.4, 0.8)
    red: float = color[0]
    if length < 0.0 or red < 0.0:
        raise AssertionError(color)

    return root


def configure_viewer(viewer: soqt.SoQtExaminerViewer, root: coin.SoNode) -> None:
    viewer.setSceneGraph(root)
    viewer.setAnimationEnabled(False)
    visible: bool = viewer.isFeedbackVisible()
    if visible:
        viewer.setFeedbackVisibility(False)
