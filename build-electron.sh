#!/bin/bash
# Electron Build Script for EEG Application
# Builds both frontend and backend into desktop apps

set -e

echo "========================================="
echo "EEG Electron Build Script"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "Project root: $PROJECT_ROOT"
echo "Frontend: $FRONTEND_DIR"
echo "Backend: $BACKEND_DIR"

# Function to print colored messages
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_deps() {
    print_status "Checking dependencies..."
    
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed"
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        print_error "npm is not installed"
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 is not installed"
        exit 1
    fi
    
    print_status "All dependencies found"
}

# Setup backend
setup_backend() {
    print_status "Setting up backend..."
    
    cd "$BACKEND_DIR"
    
    # Create virtual environment if not exists
    if [ ! -d "venv" ]; then
        print_status "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate and install dependencies
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    
    # Run migrations
    python manage.py migrate --quiet
    
    print_status "Backend setup complete"
}

# Build frontend
build_frontend() {
    print_status "Building frontend..."
    
    cd "$FRONTEND_DIR"
    
    # Install dependencies if node_modules doesn't exist
    if [ ! -d "node_modules" ]; then
        print_status "Installing npm dependencies..."
        npm install
    fi
    
    # Build for production
    npm run build
    
    print_status "Frontend build complete"
}

# Build Electron app
build_electron() {
    local TARGET=$1
    
    print_status "Building Electron app for $TARGET..."
    
    cd "$FRONTEND_DIR"
    
    # Install Electron dependencies if needed
    if ! npm list electron &> /dev/null; then
        print_status "Installing Electron dependencies..."
        npm install --save-dev electron electron-builder
    fi
    
    case $TARGET in
        linux)
            npm run electron:build:linux
            ;;
        windows)
            print_warning "Windows build requires wine on Linux"
            npm run electron:build:win
            ;;
        all)
            npm run electron:build:all
            ;;
        *)
            print_error "Unknown target: $TARGET"
            print_error "Usage: $0 [linux|windows|all]"
            exit 1
            ;;
    esac
    
    print_status "Electron build complete!"
}

# Main build function
main() {
    local TARGET=${1:-linux}
    
    print_status "Building for target: $TARGET"
    
    check_deps
    setup_backend
    build_frontend
    build_electron "$TARGET"
    
    echo ""
    echo "========================================="
    echo -e "${GREEN}Build completed successfully!${NC}"
    echo "========================================="
    echo ""
    echo "Output location:"
    echo "  $FRONTEND_DIR/release/"
    echo ""
    
    # List built files
    if [ -d "$FRONTEND_DIR/release" ]; then
        echo "Built files:"
        ls -lh "$FRONTEND_DIR/release/"
    fi
}

# Show help
show_help() {
    cat << EOF
EEG Electron Build Script

Usage: $0 [TARGET]

Targets:
  linux     Build AppImage and deb for Linux (default)
  windows   Build exe for Windows (requires wine on Linux)
  all       Build for all platforms

Examples:
  $0              # Build for Linux
  $0 linux        # Build for Linux
  $0 windows      # Build for Windows
  $0 all          # Build for all platforms

Prerequisites:
  - Node.js (v18+)
  - npm
  - Python3
  - wine (for Windows build on Linux)

EOF
}

# Handle arguments
case ${1:-linux} in
    -h|--help|help)
        show_help
        exit 0
        ;;
    linux|windows|all)
        main "$1"
        ;;
    *)
        print_error "Unknown target: $1"
        show_help
        exit 1
        ;;
esac
