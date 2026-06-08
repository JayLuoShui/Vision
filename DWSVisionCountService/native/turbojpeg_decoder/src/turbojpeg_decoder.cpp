#include <turbojpeg.h>

#include <algorithm>
#include <cstddef>
#include <cstring>
#include <limits>

namespace {

class DecoderHandle {
public:
    DecoderHandle() : handle_(tjInitDecompress()) {}

    ~DecoderHandle() {
        if (handle_ != nullptr) {
            tjDestroy(handle_);
        }
    }

    tjhandle get() const {
        return handle_;
    }

private:
    tjhandle handle_;
};

thread_local DecoderHandle decoder;

void write_error(char* output, std::size_t capacity, const char* message) {
    if (output == nullptr || capacity == 0) {
        return;
    }
    const char* source = message != nullptr ? message : "unknown TurboJPEG error";
    const std::size_t length = std::min(capacity - 1, std::strlen(source));
    std::memcpy(output, source, length);
    output[length] = '\0';
}

int read_header(
    const unsigned char* jpeg_data,
    std::size_t jpeg_size,
    int* width,
    int* height,
    char* error,
    std::size_t error_capacity
) {
    if (decoder.get() == nullptr) {
        write_error(error, error_capacity, "tjInitDecompress failed");
        return 1;
    }
    if (jpeg_data == nullptr || jpeg_size == 0 || width == nullptr || height == nullptr) {
        write_error(error, error_capacity, "invalid decode arguments");
        return 2;
    }
    if (jpeg_size > std::numeric_limits<unsigned long>::max()) {
        write_error(error, error_capacity, "JPEG data is too large");
        return 3;
    }

    int subsampling = 0;
    int color_space = 0;
    const int result = tjDecompressHeader3(
        decoder.get(),
        jpeg_data,
        static_cast<unsigned long>(jpeg_size),
        width,
        height,
        &subsampling,
        &color_space
    );
    if (result != 0) {
        write_error(error, error_capacity, tjGetErrorStr2(decoder.get()));
        return 4;
    }
    if (*width <= 0 || *height <= 0) {
        write_error(error, error_capacity, "invalid JPEG dimensions");
        return 5;
    }
    return 0;
}

}

extern "C" __declspec(dllexport) int dws_turbojpeg_get_info(
    const unsigned char* jpeg_data,
    std::size_t jpeg_size,
    int* width,
    int* height,
    char* error,
    std::size_t error_capacity
) {
    return read_header(
        jpeg_data,
        jpeg_size,
        width,
        height,
        error,
        error_capacity
    );
}

extern "C" __declspec(dllexport) int dws_turbojpeg_decode_bgr(
    const unsigned char* jpeg_data,
    std::size_t jpeg_size,
    unsigned char* output,
    std::size_t output_capacity,
    int width,
    int height,
    char* error,
    std::size_t error_capacity
) {
    int actual_width = 0;
    int actual_height = 0;
    const int header_result = read_header(
        jpeg_data,
        jpeg_size,
        &actual_width,
        &actual_height,
        error,
        error_capacity
    );
    if (header_result != 0) {
        return header_result;
    }
    if (output == nullptr || width != actual_width || height != actual_height) {
        write_error(error, error_capacity, "output dimensions do not match JPEG");
        return 6;
    }

    const std::size_t required_capacity =
        static_cast<std::size_t>(width) * static_cast<std::size_t>(height) * 3;
    if (output_capacity < required_capacity) {
        write_error(error, error_capacity, "output buffer is too small");
        return 7;
    }

    const int result = tjDecompress2(
        decoder.get(),
        jpeg_data,
        static_cast<unsigned long>(jpeg_size),
        output,
        width,
        width * 3,
        height,
        TJPF_BGR,
        0
    );
    if (result != 0) {
        write_error(error, error_capacity, tjGetErrorStr2(decoder.get()));
        return 8;
    }
    return 0;
}
