cmake_minimum_required(VERSION 3.16)
project(OCC_Receiver_Demod LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find OpenCV (optional C++ acceleration module for Stage 1-4 demodulation)
find_package(OpenCV QUIET)

if(OpenCV_FOUND)
    message(STATUS "OpenCV found: ${OpenCV_VERSION}")
    include_directories(${OpenCV_INCLUDE_DIRS})
    
    # Placeholder executable target for C++ demodulator engine
    # add_executable(occ_demod_hud src/main.cpp src/pipeline.cpp)
    # target_link_libraries(occ_demod_hud ${OpenCV_LIBS})
else()
    message(WARNING "OpenCV not found. If running C++ implementation, ensure libopencv-dev is installed.")
endif()
