#!/bin/bash

# NarrativeHive Deployment Script for Alpine Linux with existing nginx
# Usage: ./deploy.sh [--prod] [--backup] [--restore <path>] [--build-only] [--stop] [--restart] [--logs] [--status]

set -e

# Configuration
PROJECT_NAME="narrativehive"
DOMAIN="narrativehive.skumyol.com"
BACKEND_PORT=5006
FRONTEND_PORT=5176
DATA_DIR="/opt/narrativehive/data"
BACKUP_DIR="/opt/narrativehive/backups"

# Default compose file
COMPOSE_FILE="docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
PROD_MODE=false
BACKUP_DATA=false
RESTORE_FROM=""
BUILD_ONLY=false
STOP_ONLY=false
RESTART_ONLY=false
SHOW_LOGS=false
SHOW_STATUS=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --prod|--production)
      PROD_MODE=true
      COMPOSE_FILE="docker-compose.prod.yml"
      shift
      ;;
    --backup)
      BACKUP_DATA=true
      shift
      ;;
    --restore)
      RESTORE_FROM="$2"
      shift 2
      ;;
    --build-only)
      BUILD_ONLY=true
      shift
      ;;
    --stop)
      STOP_ONLY=true
      shift
      ;;
    --restart)
      RESTART_ONLY=true
      shift
      ;;
    --logs)
      SHOW_LOGS=true
      shift
      ;;
    --status)
      SHOW_STATUS=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --prod, --production    Use production configuration with persistent volumes"
      echo "  --backup               Backup data before deployment"
      echo "  --restore <path>       Restore data from backup"
      echo "  --build-only           Only build images, don't deploy"
      echo "  --stop                 Stop all containers"
      echo "  --restart              Restart all containers"
      echo "  --logs                 Show container logs"
      echo "  --status               Show container status"
      echo "  -h, --help             Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Get docker compose command
get_docker_compose_cmd() {
    if docker compose version &> /dev/null; then
        echo "docker compose"
    else
        echo "docker-compose"
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if running as root or with sudo access
    if [[ $EUID -ne 0 ]] && ! sudo -n true 2>/dev/null; then
        error "This script requires root privileges or sudo access for nginx operations"
    fi
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check if docker-compose is available
    if ! docker compose version &> /dev/null && ! docker-compose version &> /dev/null; then
        error "Docker Compose is not available. Please install Docker Compose."
    fi
    
    # Check if nginx is running
    if ! pgrep nginx > /dev/null; then
        error "Nginx is not running. Please start nginx first."
    fi
    
    # Check if SSL certificates exist
    if [[ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
        warn "SSL certificate not found for $DOMAIN. HTTPS will not work."
    fi
    
    # Check compose file exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        error "Compose file $COMPOSE_FILE not found"
    fi
    
    log "Prerequisites check completed"
}

# Setup data directories for production
setup_production_directories() {
    if [ "$PROD_MODE" = true ]; then
        log "Setting up production data directories..."
        
        # Create data directories
        mkdir -p "$DATA_DIR"/{databases,metrics,static,logs}
        mkdir -p "$DATA_DIR/metrics/deep_analysis"
        mkdir -p "$DATA_DIR/static/avatars"
        mkdir -p "$BACKUP_DIR"
        
        # Set proper permissions
        chown -R 1000:1000 "$DATA_DIR"
        chmod -R 755 "$DATA_DIR"
        
        log "Production directories created"
    fi
}

# Backup existing data
backup_data() {
    if [ "$BACKUP_DATA" = true ]; then
        log "Creating backup..."
        
        local backup_name="narrativehive-backup-$(date +%Y%m%d-%H%M%S)"
        local backup_path="$BACKUP_DIR/$backup_name"
        
        mkdir -p "$backup_path"
        
        # Backup docker volumes or data directories
        if [ "$PROD_MODE" = true ] && [ -d "$DATA_DIR" ]; then
            cp -r "$DATA_DIR"/* "$backup_path/"
        else
            # Backup docker volumes
            local docker_cmd=$(get_docker_compose_cmd)
            $docker_cmd -f "$COMPOSE_FILE" exec backend sh -c "tar czf /app/backup.tar.gz databases metrics static" 2>/dev/null || warn "Could not create backup from container"
            if [ -f "backup.tar.gz" ]; then
                mv backup.tar.gz "$backup_path/"
            fi
        fi
        
        log "Backup created at $backup_path"
    fi
}

# Restore data from backup
restore_data() {
    if [ -n "$RESTORE_FROM" ]; then
        log "Restoring data from $RESTORE_FROM..."
        
        if [ ! -d "$RESTORE_FROM" ]; then
            error "Backup directory $RESTORE_FROM not found"
        fi
        
        if [ "$PROD_MODE" = true ]; then
            cp -r "$RESTORE_FROM"/* "$DATA_DIR/"
            chown -R 1000:1000 "$DATA_DIR"
        else
            warn "Restore for non-production mode not fully implemented"
        fi
        
        log "Data restored from backup"
    fi
}

# Build Docker images
build_images() {
    log "Building Docker images..."
    
    local docker_cmd=$(get_docker_compose_cmd)
    $docker_cmd -f "$COMPOSE_FILE" build --no-cache
    
    log "Docker images built successfully"
}

# Stop existing containers
stop_containers() {
    log "Stopping existing containers..."
    
    local docker_cmd=$(get_docker_compose_cmd)
    $docker_cmd -f "$COMPOSE_FILE" down --remove-orphans
    
    log "Containers stopped"
}

# Start containers
start_containers() {
    log "Starting containers..."
    
    local docker_cmd=$(get_docker_compose_cmd)
    $docker_cmd -f "$COMPOSE_FILE" up -d
    
    log "Containers started"
}

# Update nginx configuration
update_nginx_config() {
    log "Updating nginx configuration..."
    
    local nginx_config="/etc/nginx/http.d/narrativehive.skumyol.com.conf"
    
    # Create updated nginx configuration
    cat > "$nginx_config" << EOF
server {
    server_name narrativehive.skumyol.com;
    
    # Frontend - React app
    location / {
        proxy_pass http://localhost:$FRONTEND_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # Enable CORS for frontend
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods 'GET, POST, OPTIONS, PUT, DELETE';
        add_header Access-Control-Allow-Headers 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
    }

    # Backend API - Python Flask
    location /api/ {
        proxy_pass http://localhost:$BACKEND_PORT/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # Enable CORS for API
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods 'GET, POST, OPTIONS, PUT, DELETE';
        add_header Access-Control-Allow-Headers 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
        
        # Handle preflight requests
        if (\$request_method = 'OPTIONS') {
            add_header Access-Control-Allow-Origin *;
            add_header Access-Control-Allow-Methods 'GET, POST, OPTIONS, PUT, DELETE';
            add_header Access-Control-Allow-Headers 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
            add_header Access-Control-Max-Age 1728000;
            add_header Content-Type 'text/plain; charset=utf-8';
            add_header Content-Length 0;
            return 204;
        }
    }

    # SSE endpoints for real-time updates
    location /api/stream {
        proxy_pass http://localhost:$BACKEND_PORT/api/stream;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;

        # Disable buffering for SSE
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        chunked_transfer_encoding off;

        # CORS headers
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods 'GET, POST, OPTIONS, PUT, DELETE';
        add_header Access-Control-Allow-Headers 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/narrativehive.skumyol.com/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/narrativehive.skumyol.com/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}

server {
    if (\$host = narrativehive.skumyol.com) {
        return 301 https://\$host\$request_uri;
    } # managed by Certbot

    listen 80;
    server_name narrativehive.skumyol.com;
    return 404; # managed by Certbot
}
EOF
    
    # Test nginx configuration
    if ! nginx -t; then
        error "Nginx configuration test failed"
    fi
    
    # Reload nginx
    systemctl reload nginx
    
    log "Nginx configuration updated and reloaded"
}

# Check service health
check_health() {
    log "Checking service health..."
    
    # Wait a bit for services to start
    sleep 10
    
    # Check backend health
    local backend_health_url="http://localhost:$BACKEND_PORT/api/health"
    if curl -f "$backend_health_url" > /dev/null 2>&1; then
        log "✅ Backend health check passed"
    else
        warn "❌ Backend health check failed"
    fi
    
    # Check frontend
    local frontend_url="http://localhost:$FRONTEND_PORT"
    if curl -f "$frontend_url" > /dev/null 2>&1; then
        log "✅ Frontend health check passed"
    else
        warn "❌ Frontend health check failed"
    fi
    
    # Check HTTPS
    local https_url="https://$DOMAIN"
    if curl -f "$https_url" > /dev/null 2>&1; then
        log "✅ HTTPS endpoint accessible"
    else
        warn "❌ HTTPS endpoint check failed"
    fi
}

# Show container status
show_status() {
    info "Container Status:"
    local docker_cmd=$(get_docker_compose_cmd)
    $docker_cmd -f "$COMPOSE_FILE" ps
}

# Show logs
show_logs() {
    info "Container Logs:"
    local docker_cmd=$(get_docker_compose_cmd)
    $docker_cmd -f "$COMPOSE_FILE" logs --tail=50
}

# Cleanup old images
cleanup() {
    log "Cleaning up old Docker images..."
    docker image prune -f
    log "Cleanup completed"
}

# Main deployment process
main() {
    echo -e "${BLUE}🚀 Deploying NarrativeHive to ${DOMAIN}${NC}"
    if [ "$PROD_MODE" = true ]; then
        echo -e "${YELLOW}📦 Production mode enabled${NC}"
    fi
    
    # Handle specific actions
    if [ "$STOP_ONLY" = true ]; then
        check_prerequisites
        stop_containers
        exit 0
    fi
    
    if [ "$SHOW_LOGS" = true ]; then
        show_logs
        exit 0
    fi
    
    if [ "$SHOW_STATUS" = true ]; then
        show_status
        exit 0
    fi
    
    if [ "$RESTART_ONLY" = true ]; then
        check_prerequisites
        stop_containers
        start_containers
        check_health
        exit 0
    fi
    
    # Full deployment process
    check_prerequisites
    setup_production_directories
    backup_data
    restore_data
    
    if [ "$BUILD_ONLY" = true ]; then
        build_images
        log "✅ Build completed"
        exit 0
    fi
    
    build_images
    stop_containers
    start_containers
    update_nginx_config
    check_health
    cleanup
    
    log "🎉 Deployment completed successfully!"
    log "🌐 Application available at: https://$DOMAIN"
    log "📊 Backend API: https://$DOMAIN/api/health"
    
    if [ "$PROD_MODE" = true ]; then
        log "💾 Data directory: $DATA_DIR"
        log "💾 Backup directory: $BACKUP_DIR"
    fi
}

# Run main function
main "$@"
