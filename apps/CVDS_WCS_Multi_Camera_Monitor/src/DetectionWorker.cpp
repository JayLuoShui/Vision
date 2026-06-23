// DetectionWorker is kept as a named architecture seam for the standalone WCS app.
// The current runtime still delegates detection to gpu_infer_worker.py through
// InferenceManager. Future C++ TensorRT / ONNXRuntime-GPU code should move here.
namespace cvds_wcs {
void keepDetectionWorkerTranslationUnit() {}
}  // namespace cvds_wcs
