# WCS Multi-Camera Monitor Second Stage

This short English note mirrors the Chinese deployment note and is mainly used by code search and reviewers.

## New executable

The build now keeps the original single-source tool and adds a dedicated WCS multi-camera program:

```text
CVDS_Cpp_Detector
CVDS_WCS_Multi_Camera_Monitor
```

## New runtime modules

- `CameraWorker`: per-camera video decoding, RTSP reconnect, target FPS limiting, and runtime snapshots.
- `CameraTileWidget`: reusable Qt tile for multi-camera preview and alarm highlighting.
- `WcsInferenceManager`: process-based multi-camera inference orchestration that reuses the existing detector worker.
- `WcsMonitorWindow`: WCS operator UI with configuration loading, camera table, 2x2/3x3/4x4 grid layout, preview control, monitoring control, and WCS event forwarding.

## Event pipeline

```text
worker payload
  -> WcsInferenceManager
  -> camera_id + roi_id dashboard aggregation
  -> WcsFlowUpdate / WcsJamEvent / CameraRuntimeSnapshot
  -> WcsTcpClient
  -> WCS TCP JSON
```

## Scope boundary

This stage intentionally keeps the inference path process-based for deployment safety. A future phase can replace it with a native C++ TensorRT/ONNXRuntime-GPU batch inference engine.
