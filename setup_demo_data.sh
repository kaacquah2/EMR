#!/usr/bin/env bash
# Quick setup script to generate and load synthetic demo data into MedSync

set -e

echo "🏥 MedSync Demo Data Setup"
echo "=========================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the EMR repo root
if [ ! -f "manage.py" ]; then
    echo -e "${RED}❌ Error: Must run from EMR repository root${NC}"
    echo "   cd /path/to/EMR"
    exit 1
fi

# Step 1: Generate synthetic data
echo -e "\n${YELLOW}Step 1: Generating synthetic patient data...${NC}"
if [ ! -f "demo_patients.json" ]; then
    python ml/generate_demo_patients.py --count=150
else
    echo "   ℹ️  demo_patients.json already exists, skipping generation"
    echo "   (Delete it to regenerate: rm demo_patients.json)"
fi

# Step 2: Start backend (if not running)
echo -e "\n${YELLOW}Step 2: Checking backend server...${NC}"
cd medsync-backend

if ! python manage.py check &>/dev/null; then
    echo -e "${RED}❌ Backend is not configured properly${NC}"
    exit 1
fi

# Try to connect to DB
python manage.py migrate --no-input 2>/dev/null || true

# Step 3: Load data
echo -e "\n${YELLOW}Step 3: Loading patients into database...${NC}"
python manage.py load_demo_patients --file=../demo_patients.json

cd ..

# Step 4: Instructions
echo -e "\n${GREEN}✅ Setup complete!${NC}"
echo -e "\n${YELLOW}Next steps:${NC}"
echo "  1. Start backend:  cd medsync-backend && python manage.py runserver"
echo "  2. Start frontend: cd medsync-frontend && npm run dev"
echo "  3. Open http://localhost:3000"
echo "  4. Login with: doctor@medsync.gh / Doctor123!@#"
echo -e "\n${YELLOW}To generate different data volumes:${NC}"
echo "  python ml/generate_demo_patients.py --count=500 --output=large_demo.json"
echo "  python manage.py load_demo_patients --file=large_demo.json --clear"
