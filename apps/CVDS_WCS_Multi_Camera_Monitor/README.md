# CVDS WCS Multi Camera Monitor

Standalone WCS-side multi-camera monitor.

## Runtime model format

Only OpenVINO IR is accepted at runtime.

## Output files

- cvds_online_parcel_flow_monitor.mp4
- flow_events.csv
- jam_signals.jsonl
- flow_summary.json
- cvds_preview.jpg

## Build example

```powershell
cmake -S .\apps\CVDS_WCS_Multi_Camera_Monitor -B .\build\wcs_openvino -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_DIR%;%OPENCV_DIR%;%OPENVINO_DIR%"
cmake --build .\build\wcs_openvino --config Release --target CVDS_WCS_Multi_Camera_Monitor
```
