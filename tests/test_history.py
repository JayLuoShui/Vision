from cvds_annotation_tool.models.annotation import Annotation
from cvds_annotation_tool.models.history import HistoryManager, Snapshot


def test_history_undo_redo_roundtrip():
    history = HistoryManager(max_size=10)
    empty = Snapshot(annotations=[], defects=[], selected=-1, selected_defect=-1)
    one = Snapshot(annotations=[Annotation.from_box(0, 1, 1, 2, 2)], defects=[], selected=0, selected_defect=-1)

    history.push(empty)
    undone = history.undo(one)
    redone = history.redo(empty)

    assert undone == empty
    assert redone == one
