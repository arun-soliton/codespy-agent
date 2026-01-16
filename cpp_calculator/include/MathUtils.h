#ifndef MATHUTILS_H
#define MATHUTILS_H

namespace Utils {
    class MathUtils {
    public:
        // Basic arithmetic operations
        static double add(double a, double b);
        static double subtract(double a, double b);
        static double multiply(double a, double b);
        static double divide(double a, double b);
        
        // Additional utility functions
        static double power(double base, int exponent);
        static bool isEven(int number);
    };
}

#endif // MATHUTILS_H
