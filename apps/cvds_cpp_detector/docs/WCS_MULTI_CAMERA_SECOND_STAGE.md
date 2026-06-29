# WCS Notes

This note documents the WCS-related code that still lives inside `apps/cvds_cpp_detector`.

## Current state

The current CMake target builds one executable only:

```text
CVDS_Cpp_Detector.exe
```

There is no separate `CVDS_WCS_Multi_Camera_Monitor` executable in the current build.

## WCS modules

- `WcsConfig.*`: WCS endpoint, camera and multi-camera configuration structs.
- `WcsMessage.*`: JSON payload builders for heartbeat, camera status, flow update, jam events and errors.
- `WcsTcpClient.*`: newline-delimited TCP JSON client with reconnect and queueing.
- `pipeline/WcsPayloadPublisher.*`: optional publisher used by the native video pipeline.
- `pipeline/DashboardPayloadBuilder.*`: converts runtime states into dashboard payloads.

## Runtime pipeline

```text
VideoPipeline
  -> FlowCounter / JamDetector
  -> DashboardPayloadBuilder
  -> optional WcsPayloadPublisher
  -> WCS TCP JSON
```

## Boundary

Old documentation described a process-based worker WCS stage. That is not the current runtime. The current runtime is native C++ OpenVINO/TensorRT inside `CVDS_Cpp_Detector.exe`.
