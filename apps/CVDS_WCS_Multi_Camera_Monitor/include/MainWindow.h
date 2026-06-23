#pragma once

#include "WcsMonitorWindow.h"

// Transitional alias:
// The WCS monitor has already been implemented as WcsMonitorWindow in the shared
// cvds_cpp_detector source set. The standalone app exposes it as MainWindow so
// future refactors can move the implementation here without changing main.cpp.
using MainWindow = WcsMonitorWindow;
