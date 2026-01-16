# Compile the calculator
# Usage: .\build.ps1

Write-Host "Building C++ Calculator..." -ForegroundColor Green

# Compile with g++
g++ -I.\include -o calculator.exe src\main.cpp src\Calculator.cpp src\MathUtils.cpp

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build successful! Run with: .\calculator.exe" -ForegroundColor Green
} else {
    Write-Host "Build failed!" -ForegroundColor Red
}
