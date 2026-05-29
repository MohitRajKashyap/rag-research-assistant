#!/bin/bash
# ============================================================
# start.sh — Start the full RAG Research Assistant locally
# Usage: ./scripts/start.sh [backend|frontend|docker|all]
# ============================================================

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

MODE=${1:-all}
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# -------------------------------------------------------
setup_backend() {
    info "Setting up backend..."
    cd "$ROOT_DIR/backend"

    [ ! -d "venv" ] && python3.11 -m venv venv && success "Virtual env created"
    source venv/bin/activate

    pip install -q -r requirements.txt && success "Dependencies installed"

    [ ! -f ".env" ] && cp .env.example .env && warn ".env created from .env.example — fill in your OPENAI_API_KEY!"

    mkdir -p data/uploads data/faiss_index

    info "Running Alembic migrations..."
    alembic upgrade head && success "Migrations done"
}

start_backend() {
    info "Starting FastAPI backend on :8000..."
    cd "$ROOT_DIR/backend"
    source venv/bin/activate
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    success "Backend PID: $BACKEND_PID"
}

start_celery() {
    info "Starting Celery worker..."
    cd "$ROOT_DIR/backend"
    source venv/bin/activate
    celery -A app.workers.tasks.celery_app worker --loglevel=info --concurrency=2 &
    success "Celery started"
}

setup_frontend() {
    info "Setting up frontend..."
    cd "$ROOT_DIR/frontend"
    npm install && success "Node modules installed"
    [ ! -f ".env" ] && echo "VITE_API_URL=/api/v1" > .env
}

start_frontend() {
    info "Starting React dev server on :5173..."
    cd "$ROOT_DIR/frontend"
    npm run dev &
    success "Frontend started"
}

start_docker() {
    info "Starting with Docker Compose..."
    cd "$ROOT_DIR"
    [ ! -f "backend/.env" ] && cp backend/.env.example backend/.env && warn "Configure backend/.env before running!"
    docker compose up --build -d
    success "Stack started. Visit http://localhost"
    docker compose logs -f
}

case $MODE in
    backend)
        setup_backend
        start_backend
        start_celery
        wait
        ;;
    frontend)
        setup_frontend
        start_frontend
        wait
        ;;
    docker)
        start_docker
        ;;
    all)
        setup_backend
        setup_frontend
        start_backend
        start_celery
        start_frontend
        echo ""
        success "All services started!"
        echo -e "  ${BLUE}API:${NC}      http://localhost:8000"
        echo -e "  ${BLUE}Docs:${NC}     http://localhost:8000/api/docs"
        echo -e "  ${BLUE}Frontend:${NC} http://localhost:5173"
        echo -e "  ${BLUE}Flower:${NC}   http://localhost:5555"
        wait
        ;;
    *)
        error "Unknown mode: $MODE. Use: backend|frontend|docker|all"
        ;;
esac
