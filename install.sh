#!/bin/bash
set -e

echo "======================================"
echo "    Installing EssaCache Server       "
echo "======================================"
echo ""

# Ensure we are in the correct directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Checking Python 3..."
if ! command -v python3 &> /dev/null
then
    echo "Error: Python 3 could not be found. Please install Python 3 and try again."
    exit 1
fi

echo "Installing dependencies and packaging the CLI/Server globally..."
pip install -e .

echo ""
echo "✅ Installation Complete!"
echo "======================================"
echo "🚀 Run the server anytime using:  essacache-server"
echo "💻 Run the Custom CLI using:      essacli.py"
echo "======================================"
