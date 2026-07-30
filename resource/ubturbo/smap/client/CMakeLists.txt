cmake_minimum_required(VERSION 3.13)

project(smap_client_nc)

set(CMAKE_INSTALL_PREFIX ${CMAKE_CURRENT_LIST_DIR}/output)
set(TARGET_INSTALL_BIN_DIR ${CMAKE_CURRENT_LIST_DIR}/output/bin)

include_directories(${CMAKE_CURRENT_LIST_DIR} ${CMAKE_CURRENT_LIST_DIR}/diagnose)

aux_source_directory(${CMAKE_CURRENT_LIST_DIR} SMAP_CLIENT_NC_SRCS)
aux_source_directory(${CMAKE_CURRENT_LIST_DIR}/diagnose SMAP_CLIENT_NC_SRCS)


add_executable(smap_client_nc ${SMAP_CLIENT_NC_SRCS})
target_link_libraries(smap_client_nc PUBLIC smap)

install(TARGETS smap_client_nc)