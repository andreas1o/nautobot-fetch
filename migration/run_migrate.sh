#!/bin/bash
# Helper script to run the migration tool with venv activated
# Usage: ./run_migrate.sh [options]
# Example: ./run_migrate.sh --dry-run
#          ./run_migrate.sh --config config.yaml
#          ./run_migrate.sh --objects tags,sites,devices

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/venv"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    echo ""
    echo "Please create it first:"
    echo "  cd $PROJECT_ROOT"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate venv
source "$VENV_PATH/bin/activate"

# Check if config exists, use default if not specified
CONFIG_ARG=""
if [[ ! "$*" =~ "--config" ]] && [[ ! "$*" =~ "-c" ]]; then
    if [ -f "$SCRIPT_DIR/config.yaml" ]; then
        CONFIG_ARG="--config $SCRIPT_DIR/config.yaml"
    else
        echo "Warning: No config.yaml found. Please create one:"
        echo "  cp config.yaml.example config.yaml"
        echo "  # Edit config.yaml with your credentials"
        echo ""
    fi
fi

# Run the migration
cd "$SCRIPT_DIR"
python migrate.py $CONFIG_ARG "$@"
