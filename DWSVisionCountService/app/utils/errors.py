"""Custom exceptions with error codes for DWSVisionCountService."""

from __future__ import annotations


class VisionServiceError(Exception):
    """Base exception for the vision service."""

    def __init__(self, code: int = 5000, message: str = "Unknown error"):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class ImageDecodeError(VisionServiceError):
    """Image byte decode failure."""

    def __init__(self, message: str = "Image decode failed"):
        super().__init__(code=1002, message=message)


class ImageByteLengthMismatchError(VisionServiceError):
    """Byte length mismatch between header claim and actual data."""

    def __init__(self, message: str = "Image byte length mismatch"):
        super().__init__(code=1003, message=message)


class RawImageParamMissingError(VisionServiceError):
    """Raw image mode missing required width/height/channels."""

    def __init__(self, message: str = "Missing raw image parameters"):
        super().__init__(code=1004, message=message)


class ModelNotLoadedError(VisionServiceError):
    """Inference requested but model is not ready."""

    def __init__(self, message: str = "Model not loaded"):
        super().__init__(code=1005, message=message)


class InferenceError(VisionServiceError):
    """Model inference failed."""

    def __init__(self, message: str = "Inference failed"):
        super().__init__(code=1006, message=message)


class PostprocessError(VisionServiceError):
    """Post-processing failed."""

    def __init__(self, message: str = "Post-processing failed"):
        super().__init__(code=1007, message=message)


class ImageTooLargeError(VisionServiceError):
    """Image exceeds max allowed size."""

    def __init__(self, message: str = "Image too large"):
        super().__init__(code=1008, message=message)


class HeaderParseError(VisionServiceError):
    """Header JSON parsing failed."""

    def __init__(self, message: str = "Header JSON parse failed"):
        super().__init__(code=1009, message=message)


class ImageEmptyError(VisionServiceError):
    """Decoded image is empty or None."""

    def __init__(self, message: str = "Image is empty"):
        super().__init__(code=1001, message=message)


class VisionPipelineError(VisionServiceError):
    """Vision pipeline error (preprocess/inference/postprocess)."""

    def __init__(self, message: str = "Vision pipeline error"):
        super().__init__(code=5001, message=message)
