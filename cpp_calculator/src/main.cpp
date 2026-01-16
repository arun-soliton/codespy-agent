#include <iostream>
#include "Calculator.h"

int main() {
    Calculator calc;
    
    std::cout << "=== Calculator Demo ===" << std::endl;
    std::cout << "Initial value: " << calc.getValue() << std::endl << std::endl;
    
    // Perform operations
    calc.add(10);
    std::cout << "After " << calc.getLastOperation() << ": " << calc.getValue() << std::endl;
    
    calc.multiply(5);
    std::cout << "After " << calc.getLastOperation() << ": " << calc.getValue() << std::endl;
    
    calc.subtract(20);
    std::cout << "After " << calc.getLastOperation() << ": " << calc.getValue() << std::endl;
    
    calc.divide(10);
    std::cout << "After " << calc.getLastOperation() << ": " << calc.getValue() << std::endl;
    
    calc.powerOf(2);
    std::cout << "After " << calc.getLastOperation() << ": " << calc.getValue() << std::endl;
    
    // Check if even
    std::cout << std::endl;
    calc.checkIfResultIsEven();
    
    // Test division by zero
    std::cout << std::endl << "Testing division by zero:" << std::endl;
    calc.divide(0);
    
    // Reset
    std::cout << std::endl;
    calc.reset();
    std::cout << "After reset: " << calc.getValue() << std::endl;
    
    return 0;
}
