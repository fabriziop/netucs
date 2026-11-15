cmake_minimum_required(VERSION 3.18)
project(netucs LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(Threads REQUIRED)

# Conductor must be installed separately (headers AND native static library).
# Honor CMAKE_PREFIX_PATH, CONDUCTOR_ROOT and explicit cache overrides.
set(CONDUCTOR_ROOT "" CACHE PATH "Conductor installation prefix (e.g. /usr/local)")
set(_conductor_prefixes "${CONDUCTOR_ROOT}" "$ENV{CONDUCTOR_ROOT}")
find_path(CONDUCTOR_INCLUDE_DIR NAMES conductor/scheduler.hpp
  HINTS ${_conductor_prefixes} PATH_SUFFIXES include)
find_library(CONDUCTOR_LIBRARY NAMES conductor
  HINTS ${_conductor_prefixes} PATH_SUFFIXES lib lib64 lib/${CMAKE_LIBRARY_ARCHITECTURE})
if(NOT CONDUCTOR_INCLUDE_DIR OR NOT CONDUCTOR_LIBRARY)
  message(FATAL_ERROR
    "Conductor C++ development files were not found.\n"
    "Expected: <prefix>/include/conductor/scheduler.hpp and <prefix>/lib/libconductor.a\n"
    "Installing the Python conductor module alone is insufficient.\n"
    "Install the Conductor C++ library and headers (in the Conductor source: "
    "cmake -S . -B build -DCONDUCTOR_BUILD_PYTHON=OFF && "
    "cmake --build build && sudo cmake --install build).\n"
    "If already installed elsewhere, pass -DCONDUCTOR_ROOT=/prefix, or "
    "-DCONDUCTOR_INCLUDE_DIR=/path/to/include -DCONDUCTOR_LIBRARY=/path/to/libconductor.a")
endif()
message(STATUS "Conductor headers: ${CONDUCTOR_INCLUDE_DIR}")
message(STATUS "Conductor library: ${CONDUCTOR_LIBRARY}")
if(NOT TARGET conductor::conductor)
  add_library(conductor::conductor UNKNOWN IMPORTED)
  set_target_properties(conductor::conductor PROPERTIES
    IMPORTED_LOCATION "${CONDUCTOR_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${CONDUCTOR_INCLUDE_DIR}"
    INTERFACE_LINK_LIBRARIES Threads::Threads)
endif()

add_library(netucs STATIC cpp/network.cpp cpp/value.cpp)
add_library(netucs::netucs ALIAS netucs)
target_include_directories(netucs PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_link_libraries(netucs PUBLIC conductor::conductor Threads::Threads)
set_target_properties(netucs PROPERTIES POSITION_INDEPENDENT_CODE ON)
option(NETUCS_BUILD_PYTHON "Build pybind11 extension" ON)
if(NETUCS_BUILD_PYTHON)
  find_package(pybind11 CONFIG REQUIRED)
  pybind11_add_module(_netucs_native cpp/bindings.cpp)
  target_link_libraries(_netucs_native PRIVATE netucs)
  install(TARGETS _netucs_native LIBRARY DESTINATION netucs)
endif()
install(TARGETS netucs EXPORT netucsTargets ARCHIVE DESTINATION lib)
install(EXPORT netucsTargets NAMESPACE netucs:: DESTINATION lib/cmake/netucs)
install(DIRECTORY include/netucs DESTINATION include)
option(NETUCS_BUILD_TESTS "Build native smoke test" OFF)
if(NETUCS_BUILD_TESTS)
  enable_testing()
  add_executable(netucs_smoke tests/cpp/smoke.cpp)
  target_link_libraries(netucs_smoke PRIVATE netucs)
  add_test(NAME netucs_smoke COMMAND netucs_smoke)
  add_executable(netucs_value_test tests/cpp/value.cpp)
  target_link_libraries(netucs_value_test PRIVATE netucs)
  add_test(NAME netucs_value_test COMMAND netucs_value_test)
endif()
