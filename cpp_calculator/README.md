# C++ Calculator Project

A simple C++ calculator demonstrating object-oriented programming with modular design.

## Project Structure

```
cpp_calculator/
├── include/          # Header files
│   ├── Calculator.h
│   └── MathUtils.h
├── src/             # Source files
│   ├── Calculator.cpp
│   ├── MathUtils.cpp
│   └── main.cpp
├── CMakeLists.txt   # CMake build configuration
└── README.md        # This file
```

## Components

### Calculator Class

Main class that provides a calculator with:

- Basic arithmetic operations (add, subtract, multiply, divide)
- Advanced operations (power)
- State management
- Error handling

### MathUtils Module

Helper utility class with static methods for:

- Arithmetic operations
- Power calculations
- Even/odd number checking

## Building

### Using g++ directly:

```bash
g++ -I./include -o calculator src/main.cpp src/Calculator.cpp src/MathUtils.cpp
./calculator
```

### Using CMake:

```bash
mkdir build
cd build
cmake ..
cmake --build .
./calculator
```

## Usage Example

```cpp
Calculator calc;
calc.add(10);        // Current value: 10
calc.multiply(5);    // Current value: 50
calc.subtract(20);   // Current value: 30
calc.divide(10);     // Current value: 3
calc.powerOf(2);     // Current value: 9
```
