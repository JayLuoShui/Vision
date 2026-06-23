# CVDS WCS Multi Camera Monitor

Standalone WCS-side multi-camera monitor.

## Runtime model format

Only OpenVINO IR is accepted at runtime.

## Build example

```powershell
cmake -S .\apps\CVDS_WCS_Multi_Camera_Monitor -B .\build\wcs_openvino -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_DIR%;%OPENCV_DIR%;%OPENVINO_DIR%"
cmake --build .\build\wcs_openvino --config Release --target CVDS_WCS_Multi_Camera_Monitor
```
