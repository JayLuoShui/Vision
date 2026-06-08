#pragma once

#include <atomic>
#include <functional>
#include <future>
#include <string>

struct TaskProgress {
    int done = 0;
    int total = 0;
    std::string message;
};

class TaskScheduler {
public:
    using Task = std::function<void(std::atomic_bool&, std::function<void(TaskProgress)>)>;
    std::future<void> run(Task task, std::function<void(TaskProgress)> progress);
    void cancel();

private:
    std::atomic_bool cancelRequested_ = false;
};
