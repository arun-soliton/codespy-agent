#ifndef CALCULATOR_H
#define CALCULATOR_H

#include "MathUtils.h"
#include <string>

class Calculator {
private:
    double currentValue;
    std::string lastOperation;
    
    // Private helper function
    bool isPositive(double value) const;
    
public:
    // Constructor
    Calculator();
    
    // Basic operations using MathUtils
    void add(double value);
    void subtract(double value);
    void multiply(double value);
    void divide(double value);
    
    // Advanced operations
    void powerOf(int exponent);
    void reset();
    
    // Getters
    double getValue() const;
    std::string getLastOperation() const;
    
    // Utility
    void checkIfResultIsEven();
    void checkIfPositive();
};

#endif // CALCULATOR_H
