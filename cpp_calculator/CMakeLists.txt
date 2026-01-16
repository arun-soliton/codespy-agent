cmake_minimum_required(VERSION 3.10)
project(Calculator VERSION 1.0)

# Set C++ standard
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Include directories
include_directories(${PROJECT_SOURCE_DIR}/include)

# Source files
set(SOURCES
    src/main.cpp
    src/Calculator.cpp
    src/MathUtils.cpp
)

# Create executable
add_executable(calculator ${SOURCES})

# Installation (optional)
install(TARGETS calculator DESTINATION bin)
