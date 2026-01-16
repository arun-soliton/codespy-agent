#include "MathUtils.h"
#include <stdexcept>
#include <cmath>

namespace Utils {
    double MathUtils::add(double a, double b) {
        return a + b;
    }
    
    double MathUtils::subtract(double a, double b) {
        return a - b;
    }
    
    double MathUtils::multiply(double a, double b) {
        return a * b;
    }
    
    double MathUtils::divide(double a, double b) {
        if (b == 0) {
            throw std::runtime_error("Division by zero error");
        }
        return a / b;
    }
    
    double MathUtils::power(double base, int exponent) {
        return std::pow(base, exponent);
    }
    
    bool MathUtils::isEven(int number) {
        return number % 2 == 0;
    }
}
