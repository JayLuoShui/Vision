"""Vision backend base class and factories.

Defines the InferenceBackendABC abstract interface and provides
concrete implementations for Ultralytics (OpenVINO) and a stub
for native OpenVINO runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from loguru import logger

from app.config import Config
from app.vision.schemas import Detection  # Local model schema
from app.utils.errors import ModelNotLoadedError, InferenceError


class InferenceBackendABC(ABC):
    """Abstract base class for inference backends.

    All backends must:
    1. Load the model in __init__
    2. Provide `predict(input_tensor)` returning Detection objects
    3. Provide `is_ready()` to check if model loaded successfully

    Subclasses should:
    - Use cv2.dnn for raw OpenVINO IR inference if they want to avoid
      heavy dependencies like ultralytics
    - Or use the ultralytics package's OpenVINO support
    """

    @abstractmethod
    def predict(self, input_tensor: np.ndarray) -> list[Detection]:
        """Run inference on a single batch.

        Args:
            input_tensor: Input tensor, shape (1, C, H, W), normalized.

        Returns:
            List of Detection objects.
        """
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if model is loaded successfully."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release backend resources. Override in subclasses."""
        pass


class UltralyticsOpenVINOBackend(InferenceBackendABC):
    """Inference backend using Ultralytics with OpenVINO engine.

    This is the recommended backend for V1. It leverages the
    ultralytics library which handles OpenVINO model loading under
    the hood.

    Note: This requires the `ultralytics` package with OpenVINO support.
    """

    def __init__(self, config: Config):
        """Initialize and load the OpenVINO model.

        Args:
            config: Project configuration with model settings.
        """
        self.config = config
        self.model = None
        self._ready = False
        self._model_path = config.get_model_path()
        self._device = config.model.device
        self._batch = config.model.batch
        self._imgsz = config.model.imgsz

        try:
            logger.info("Loading Ultralytics model: {} on {}", self._model_path, self._device)
            
            # Import and load model
            # For OpenVINO, use *.xml file from the exported directory
            import os
            # Try to find the actual model file
            if os.path.isdir(self._model_path):
                # It's a directory (e.g., best_openvino_model)
                xml_files = [f for f in os.listdir(self._model_path) if f.endswith('.xml')]
                if xml_files:
                    self._model_path = os.path.join(self._model_path, xml_files[0])
                else:
                    # Fallback: try to find .pt in parent dir
                    logger.warning("No .xml files found in model directory, using Ultralytics .pt model")
            
            # Import ultralytics dynamically
            try:
                from ultralytics import YOLO
            except ImportError:
                logger.error("ultralytics not installed, cannot load model")
                return

            self.model = YOLO(self._model_path)
            
            # Set device and configuration (OpenVINO backends handle device internally)
            if hasattr(self.model, 'model') and hasattr(self.model.model, 'to'):
                self.model.model.to(self._device)
            if hasattr(self.model, 'model') and hasattr(self.model.model, 'fuse'):
                self.model.model.fuse()
            
            # Set parameters
            self.model.overrides['imgsz'] = [self._imgsz, self._imgsz]
            self.model.overrides['conf'] = config.model.confidence_threshold
            self.model.overrides['iou'] = config.model.iou_threshold
            
            self._ready = True
            logger.info("Ultralytics model loaded successfully from: {}", self._model_path)
        except Exception as e:
            logger.error("Failed to load model: {}", e)
            self._ready = False

    def predict(self, input_tensor: np.ndarray) -> list[Detection]:
        """Run inference using the loaded model.

        Args:
            input_tensor: Input tensor, shape (1, C, H, W), normalized.

        Returns:
            List of Prediction objects.

        Raises:
            ModelNotLoadedError: If model is not ready.
            InferenceError: If inference fails.
        """
        if not self.is_ready():
            raise ModelNotLoadedError("Model not loaded")

        try:
            # Run inference using Ultralytics
            if hasattr(self.model, 'predict'):
                results = self.model.predict(
                    source=None,  # We'll use pre-processed tensor
                    imgsz=self._imgsz,
                    conf=self.config.model.confidence_threshold,
                    iou=self.config.model.iou_threshold,
                    verbose=False,
                    device=self._device,
                    batch=1,
                    # Additional args for better performance
                    max_det=100,
                    agnostic_nms=False,
                )
            else:
                results = self.model(input_tensor)

            # Convert results to Detection objects
            return self._convert_results(results)

        except Exception as e:
            logger.error("Inference failed: {}", e)
            raise InferenceError(f"Inference failed: {e}") from e

    def is_ready(self) -> bool:
        """Check if model is loaded successfully."""
        return self._ready and self.model is not None

    def close(self) -> None:
        """Release backend resources."""
        self.model = None
        self._ready = False
        logger.info("Ultralytics backend closed")

    def _convert_results(self, results) -> list[Detection]:
        """Convert Ultralytics results to Detection objects.

        Args:
            results: Ultralytics inference results.

        Returns:
            List of Detection objects.
        """
        detections = []
        
        if not results:
            return detections

        # Handle batched results
        if isinstance(results, (list, tuple)):
            for result in results:
                if hasattr(result, 'boxes') and result.boxes is not None:
                    boxes = result.boxes
                    if hasattr(boxes, 'cls') and hasattr(boxes, 'conf'):
                        cls = boxes.cls
                        conf = boxes.conf
                        
                        # Get masks if available
                        masks = None
                        if hasattr(boxes, 'masks') and boxes.masks is not None:
                            masks = boxes.masks.data
                        
                        if hasattr(cls, 'cpu') and hasattr(conf, 'cpu'):
                            cls = cls.cpu()
                            conf = conf.cpu()
                        
                        if hasattr(masks, 'cpu') if masks is not None else True:
                            if masks is not None and hasattr(masks, 'cpu'):
                                masks = masks.cpu()

                        # Extract detections
                        for i in range(len(cls)):
                            class_id = int(cls[i]) if hasattr(cls[i], 'item') else int(cls[i])
                            score = float(conf[i]) if hasattr(conf[i], 'item') else float(conf[i])
                            
                            detections.append(Detection(
                                class_id=class_id,
                                score=score,
                                mask=masks[i] if masks is not None and i < len(masks) else None
                            ))
        
        return detections


class NativeOpenVINOBackend(InferenceBackendABC):
    """Inference backend using native OpenVINO runtime.

    This backend uses the OpenVINO Python API directly for inference.
    It provides better control and performance but requires more 
    manual implementation.

    TODO: Implement the following:
    1. Load OpenVINO model (IR format: .xml + .bin)
    2. Prepare input/output tensors
    3. Execute inference
    4. Post-process results
    
    This is a stub implementation.
    """

    def __init__(self, config: Config):
        """Initialize and load the OpenVINO model.

        Args:
            config: Project configuration with model settings.
        """
        self.config = config
        self.model = None
        self._ready = False
        self._model_path = config.get_model_path()
        self._device = config.model.device
        self._imgsz = config.model.imgsz

        # TODO: Implement native OpenVINO model loading
        logger.info("Native OpenVINO backend loaded from: {}", self._model_path)
        # For now, mark as ready using Ultralytics backend
        self._ultralytics_backend = UltralyticsOpenVINOBackend(config)
        if self._ultralytics_backend.is_ready():
            self._ready = True

    def predict(self, input_tensor: np.ndarray) -> list[Detection]:
        """Run inference using native OpenVINO runtime.

        Args:
            input_tensor: Input tensor, shape (1, C, H, W), normalized.

        Returns:
            List of Detection objects.

        Raises:
            ModelNotLoadedError: If model is not ready.
            InferenceError: If inference fails.
        """
        if not self.is_ready():
            raise ModelNotLoadedError("Model not loaded")

        try:
            # Use Ultralytics backend as fallback
            if self._ultralytics_backend and self._ultralytics_backend.is_ready():
                return self._ultralytics_backend.predict(input_tensor)
            raise InferenceError("No backend available")
        except Exception as e:
            logger.error("Inference failed: {}", e)
            raise InferenceError(f"Inference failed: {e}") from e

    def is_ready(self) -> bool:
        """Check if model is loaded successfully."""
        return self._ready and (self.model is not None or 
                                (self._ultralytics_backend and self._ultralytics_backend.is_ready()))

    def close(self) -> None:
        """Release backend resources."""
        self.model = None
        self._ultralytics_backend.close() if self._ultralytics_backend else None
        self._ready = False
        logger.info("Native OpenVINO backend closed")


def create_backend(config: Config) -> InferenceBackendABC:
    """Factory function to create inference backend.

    Args:
        config: Project configuration.

    Returns:
        InferenceBackendABC instance based on config.

    Raises:
        ValueError: If backend type is not supported.
    """
    backend_type = config.model.backend

    if backend_type == "ultralytics_openvino":
        return UltralyticsOpenVINOBackend(config)
    elif backend_type == "native_openvino":
        return NativeOpenVINOBackend(config)
    elif backend_type == "auto":
        # Auto-detect best available backend
        # For now, default to ultralytics_openvino
        return UltralyticsOpenVINOBackend(config)
    else:
        raise ValueError(f"Unsupported backend: {backend_type}")
