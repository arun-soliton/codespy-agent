#include "Calculator.h"
#include <iostream>
#include <sstream>

/**
 * @brief Constructor - Initializes the calculator with default values
 * Sets currentValue to 0.0 and lastOperation to "initialized"
 */
Calculator::Calculator() : currentValue(0.0), lastOperation("initialized") {}

/**
 * @brief Adds a value to the current calculator result
 * @param value The value to add to currentValue
 * Uses MathUtils::add for the arithmetic operation
 */
void Calculator::add(double value) {
    currentValue = Utils::MathUtils::add(currentValue, value);
    std::ostringstream oss;
    oss << "Added " << value;
    lastOperation = oss.str();
}

/**
 * @brief Subtracts a value from the current calculator result
 * @param value The value to subtract from currentValue
 * Uses MathUtils::subtract for the arithmetic operation
 */
void Calculator::subtract(double value) {
    currentValue = Utils::MathUtils::subtract(currentValue, value);
    std::ostringstream oss;
    oss << "Subtracted " << value;
    lastOperation = oss.str();
}

/**
 * @brief Multiplies the current calculator result by a value
 * @param value The value to multiply currentValue by
 * Uses MathUtils::multiply for the arithmetic operation
 */
void Calculator::multiply(double value) {
    currentValue = Utils::MathUtils::multiply(currentValue, value);
    std::ostringstream oss;
    oss << "Multiplied by " << value;
    lastOperation = oss.str();
}

/**
 * @brief Divides the current calculator result by a value
 * @param value The divisor (cannot be zero)
 * Uses MathUtils::divide and handles division by zero errors
 * Sets lastOperation to "Division error" if an exception occurs
 */
void Calculator::divide(double value) {
    try {
        currentValue = Utils::MathUtils::divide(currentValue, value);
        std::ostringstream oss;
        oss << "Divided by " << value;
        lastOperation = oss.str();
    } catch (const std::runtime_error& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        lastOperation = "Division error";
    }
}

/**
 * @brief Raises the current calculator result to a power
 * @param exponent The exponent to raise currentValue to
 * Uses MathUtils::power for the calculation
 */
void Calculator::powerOf(int exponent) {
    currentValue = Utils::MathUtils::power(currentValue, exponent);
    std::ostringstream oss;
    oss << "Raised to power " << exponent;
    lastOperation = oss.str();
}

/**
 * @brief Resets the calculator to its initial state
 * Sets currentValue to 0.0 and lastOperation to "reset"
 */
void Calculator::reset() {
    currentValue = 0.0;
    lastOperation = "reset";
}

/**
 * @brief Gets the current calculator result
 * @return The current value stored in the calculator
 */
double Calculator::getValue() const {
    return currentValue;
}

/**
 * @brief Gets the description of the last operation performed
 * @return A string describing the last operation executed
 */
std::string Calculator::getLastOperation() const {
    return lastOperation;
}

/**
 * @brief Checks if the current result is an even number
 * Casts currentValue to an integer and uses MathUtils::isEven
 * Prints the result to stdout
 */
void Calculator::checkIfResultIsEven() {
    int intValue = static_cast<int>(currentValue);
    if (Utils::MathUtils::isEven(intValue)) {
        std::cout << "Current value " << intValue << " is even" << std::endl;
    } else {
        std::cout << "Current value " << intValue << " is odd" << std::endl;
    }
}

/**
 * @brief Helper function to check if a value is positive
 * @param value The value to check
 * @return true if value is greater than 0, false otherwise
 */
bool Calculator::isPositive(double value) const {
    return value > 0;
}

/**
 * @brief Checks if the current result is positive
 * Calls the helper function isPositive and prints the result
 */
void Calculator::checkIfPositive() {
    if (isPositive(currentValue)) {
        std::cout << "Current value " << currentValue << " is positive" << std::endl;
    } else if (currentValue == 0) {
        std::cout << "Current value is zero" << std::endl;
    } else {
        std::cout << "Current value " << currentValue << " is negative" << std::endl;
    }
}
