from cvds_annotation_tool.services.dataset_export import export_dataset


def test_dataset_export_creates_train_val_structure(tmp_path):
    root = tmp_path / "source"
    export_root = tmp_path / "export"
    (root / "images" / "train").mkdir(parents=True)
    (root / "labels" / "train").mkdir(parents=True)
    for idx in range(4):
        (root / "images" / "train" / f"{idx}.jpg").write_bytes(b"fake")
        (root / "labels" / "train" / f"{idx}.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")

    result = export_dataset(root, export_root, val_ratio=0.25, include_empty=True, make_zip=True)

    assert result.train_count == 3
    assert result.val_count == 1
    assert (export_root / "images" / "train").exists()
    assert (export_root / "images" / "val").exists()
    assert (export_root / "data.yaml").exists()
    assert result.zip_path is not None and result.zip_path.exists()
