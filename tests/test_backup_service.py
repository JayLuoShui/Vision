from cvds_annotation_tool.services.backup_service import AtomicWriteError, atomic_write_text


def test_atomic_save_failure_keeps_old_file(tmp_path):
    path = tmp_path / "label.txt"
    path.write_text("old", encoding="utf-8")

    try:
        atomic_write_text(path, "new", fail_before_replace=True)
    except AtomicWriteError:
        pass

    assert path.read_text(encoding="utf-8") == "old"
