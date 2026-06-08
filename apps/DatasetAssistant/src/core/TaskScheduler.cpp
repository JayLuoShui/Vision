#include "core/TaskScheduler.h"

std::future<void> TaskScheduler::run(Task task, std::function<void(TaskProgress)> progress) {
    cancelRequested_ = false;
    return std::async(std::launch::async, [this, task = std::move(task), progress = std::move(progress)]() {
        task(cancelRequested_, progress);
    });
}

void TaskScheduler::cancel() {
    cancelRequested_ = true;
}
