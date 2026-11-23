cmake_minimum_required(VERSION 3.15)
project(ModalSelfCalV53New LANGUAGES CXX)

add_library(modalselfcal STATIC ModalSelfCal.cpp)
target_include_directories(modalselfcal PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_features(modalselfcal PUBLIC cxx_std_17)
if(MSVC)
    target_compile_options(modalselfcal PRIVATE /utf-8)
endif()

include(CTest)
if(BUILD_TESTING)
    add_executable(test_dynamic_markers tests/test_dynamic_markers.cpp)
    target_link_libraries(test_dynamic_markers PRIVATE modalselfcal)
    foreach(test_case IN ITEMS add remove missing restart legacy attachment_limits)
        add_test(NAME v53_new_${test_case}
                 COMMAND test_dynamic_markers ${test_case} "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures")
    endforeach()
endif()
