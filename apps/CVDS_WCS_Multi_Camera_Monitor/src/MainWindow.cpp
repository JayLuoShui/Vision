// Transitional implementation bridge.
// The full Qt WCS monitor window currently lives in apps/cvds_cpp_detector/src
// as WcsMonitorWindow. This standalone app compiles that implementation through
// the MainWindow facade, then future commits can move and rename the class
// without changing runtime behavior.
#include "../../cvds_cpp_detector/src/WcsMonitorWindow.cpp"
