cmake_minimum_required(VERSION 3.14)
project(ubs-mem-test VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(UBS_MEM_INCLUDE_DIR "/usr/local/ubs_mem/include")
set(UBS_MEM_LIB_DIR "/usr/local/ubs_mem/lib")

add_executable(ubs_mem_test
    src/main.cpp
    src/http_server.cpp
    src/api_handler.cpp
)

target_include_directories(ubs_mem_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${UBS_MEM_INCLUDE_DIR}
)

target_link_libraries(ubs_mem_test PRIVATE pthread ubsm_sdk ${CMAKE_DL_LIBS})

install(TARGETS ubs_mem_test DESTINATION bin)
