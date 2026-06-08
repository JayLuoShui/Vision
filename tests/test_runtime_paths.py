from cvds_annotation_tool.runtime_paths import RuntimePaths


def test_runtime_paths_use_user_appdata_and_no_developer_absolute_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))

    paths = RuntimePaths(app_name="AnnotationTool")

    assert paths.user_data_dir == tmp_path / "LocalAppData" / "CVDS" / "AnnotationTool"
    assert paths.default_output_dir == paths.user_data_dir / "datasets" / "cvds_annotation_yolo"
    assert paths.logs_dir == paths.user_data_dir / "logs"
    assert paths.backups_dir == paths.user_data_dir / "backups"
    assert paths.cache_dir == paths.user_data_dir / "cache"
    combined = "\n".join(str(value) for value in paths.as_dict().values())
    assert "C:\\Users\\shuai" not in combined
    assert "anaconda3" not in combined.lower()
