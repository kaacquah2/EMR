#!/usr/bin/env bash
# MedSync AI Module setup: install deps, run migrations, train models.
# Run from EMR repo root: ./scripts/setup_ai.sh
# Or from medsync-backend: ../scripts/setup_ai.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/medsync-backend"
MODELS_DIR="${BACKEND_DIR}/api/ai/models"
DATA_CSV=""

usage() {
  echo "Usage: $0 [OPTIONS]"
  echo "  --data-csv PATH   Optional CSV for training (not yet used; synthetic data used)"
  echo "  --models-dir DIR  Output directory for .joblib files (default: api/ai/models)"
  echo "  --skip-migrate    Do not run Django migrations"
  echo "  --skip-train      Do not train models (only install deps / migrate)"
  exit 0
}

SKIP_MIGRATE=""
SKIP_TRAIN=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --data-csv)   DATA_CSV="$2"; shift 2 ;;
    --models-dir) MODELS_DIR="$2"; shift 2 ;;
    --skip-migrate) SKIP_MIGRATE=1; shift ;;
    --skip-train)   SKIP_TRAIN=1; shift ;;
    -h|--help)     usage ;;
    *)             echo "Unknown option: $1"; usage ;;
  esac
done

if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Error: Backend directory not found: $BACKEND_DIR"
  exit 1
fi

echo "=== MedSync AI setup ==="
echo "Backend: $BACKEND_DIR"
echo "Models dir: $MODELS_DIR"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -q -r "${BACKEND_DIR}/requirements-local.txt"
echo "Dependencies OK."
echo ""

# Migrations (optional)
if [[ -z "$SKIP_MIGRATE" ]]; then
  echo "Running migrations..."
  cd "$BACKEND_DIR"
  python manage.py migrate --noinput
  echo "Migrations OK."
  cd "$REPO_ROOT"
  echo ""
fi

# Train models (optional)
if [[ -z "$SKIP_TRAIN" ]]; then
  echo "Training AI models (synthetic data)..."
  mkdir -p "$MODELS_DIR"
  cd "$BACKEND_DIR"
  if [[ -n "$DATA_CSV" ]]; then
    python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
import django
django.setup()
from api.ai.train_models import run_training
from pathlib import Path
run_training(data_path='${DATA_CSV}', output_dir=Path('${MODELS_DIR}'))
"
  else
    python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
import django
django.setup()
from api.ai.train_models import run_training
from pathlib import Path
run_training(output_dir=Path('${MODELS_DIR}'))
"
  fi
  cd "$REPO_ROOT"
  echo "Training OK. Models in $MODELS_DIR"
  ls -la "$MODELS_DIR"/*.joblib 2>/dev/null || true
  echo ""
fi

echo "=== AI setup complete ==="
echo "To use a custom models directory at runtime, set: MEDSYNC_AI_MODELS_DIR=$MODELS_DIR"
