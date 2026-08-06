#!/bin/bash
PROJ_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)

rm -rf ${PROJ_DIR}/cmake-build
rm -rf ${PROJ_DIR}/output
cmake -S ${PROJ_DIR} -B ${PROJ_DIR}/cmake-build
cmake --build ${PROJ_DIR}/cmake-build
cmake --install ${PROJ_DIR}/cmake-build