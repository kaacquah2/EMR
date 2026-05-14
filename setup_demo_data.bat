@echo off
REM Quick setup script to generate and load synthetic demo data into MedSync (Windows)

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   MedSync Demo Data Setup
echo ========================================
echo.

REM Check if we're in the EMR repo root
if not exist "manage.py" (
    echo ERROR: Must run from EMR repository root
    echo.
    echo   cd \path\to\EMR
    pause
    exit /b 1
)

REM Step 1: Generate synthetic data
echo Step 1: Generating synthetic patient data...
if not exist "medsync-backend\data\seeds\demo_patients.json" (
    python ml\generate_demo_patients.py --count=150
) else (
    echo.
    echo INFO: demo_patients.json already exists in seeds, skipping generation
    echo       Delete it to regenerate: del medsync-backend\data\seeds\demo_patients.json
    echo.
)

REM Step 2: Check backend
echo.
echo Step 2: Checking backend server...
cd medsync-backend

python manage.py check >nul 2>&1
if errorlevel 1 (
    echo ERROR: Backend is not configured properly
    cd ..
    pause
    exit /b 1
)

REM Step 3: Run migrations
python manage.py migrate --no-input >nul 2>&1

REM Step 4: Load data
echo.
echo Step 3: Loading patients into database...
python manage.py load_demo_patients --file=data\seeds\demo_patients.json

cd ..

REM Step 5: Instructions
echo.
echo ========================================
echo   SUCCESS!
echo ========================================
echo.
echo Next steps:
echo   1. Start backend:  cd medsync-backend ^& python manage.py runserver
echo   2. Start frontend: cd medsync-frontend ^& npm run dev
echo   3. Open http://localhost:3000
echo   4. Login with: doctor@medsync.gh / Doctor123!@#
echo.
echo To generate different data volumes:
echo   python ml\generate_demo_patients.py --count=500 --output=large_demo.json
echo   python medsync-backend\manage.py load_demo_patients --file=large_demo.json --clear
echo.
pause
