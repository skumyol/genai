#!/bin/bash

# NarrativeHive Volume Management Script
# Usage: ./manage-volumes.sh [backup|restore|list|cleanup] [options]

set -e

# Configuration
PROJECT_NAME="narrativehive"
DATA_DIR="/opt/narrativehive/data"
BACKUP_DIR="/opt/narrativehive/backups"
COMPOSE_FILE="docker-compose.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"; }
error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"; exit 1; }
info() { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"; }

# Get docker compose command
get_docker_compose_cmd() {
    if docker compose version &> /dev/null; then
        echo "docker compose"
    else
        echo "docker-compose"
    fi
}

# List all volumes and their sizes
list_volumes() {
    log "📊 NarrativeHive Volume Information"
    echo
    
    local docker_cmd=$(get_docker_compose_cmd)
    
    # Check if containers are running
    if $docker_cmd -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        info "Containers are running - showing live data"
        
        # Get sizes from running containers
        echo -e "${BLUE}=== Database Files ===${NC}"
        $docker_cmd -f "$COMPOSE_FILE" exec backend find /app/databases -type f -name "*.db*" -exec ls -lh {} \; 2>/dev/null || warn "Could not access database files"
        
        echo -e "\n${BLUE}=== Metrics Files ===${NC}"
        $docker_cmd -f "$COMPOSE_FILE" exec backend find /app/metrics -type f -exec ls -lh {} \; 2>/dev/null || warn "Could not access metrics files"
        
        echo -e "\n${BLUE}=== Static Files ===${NC}"
        $docker_cmd -f "$COMPOSE_FILE" exec backend find /app/static -type f -exec ls -lh {} \; 2>/dev/null || warn "Could not access static files"
        
    else
        info "Containers not running - showing persistent volume data"
        
        # Check production data directory
        if [ -d "$DATA_DIR" ]; then
            echo -e "${BLUE}=== Production Data Directory ===${NC}"
            du -sh "$DATA_DIR"/*/ 2>/dev/null || warn "Could not access data directory"
            echo
            find "$DATA_DIR" -type f -name "*.db*" -exec ls -lh {} \; 2>/dev/null
        fi
        
        # Show Docker volumes
        echo -e "\n${BLUE}=== Docker Volumes ===${NC}"
        docker volume ls | grep narrativehive || info "No named volumes found"
    fi
    
    # Show backups
    if [ -d "$BACKUP_DIR" ]; then
        echo -e "\n${BLUE}=== Available Backups ===${NC}"
        ls -lah "$BACKUP_DIR"/ 2>/dev/null || info "No backups found"
    fi
}

# Create backup
create_backup() {
    local backup_name="narrativehive-backup-$(date +%Y%m%d-%H%M%S)"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    log "📦 Creating backup: $backup_name"
    
    mkdir -p "$backup_path"
    
    local docker_cmd=$(get_docker_compose_cmd)
    
    # Check if containers are running
    if $docker_cmd -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        info "Backing up from running containers..."
        
        # Create tar from container volumes
        $docker_cmd -f "$COMPOSE_FILE" exec backend tar czf /tmp/backup.tar.gz \
            -C /app databases metrics static 2>/dev/null || warn "Could not create container backup"
        
        # Copy backup from container
        docker cp $($docker_cmd -f "$COMPOSE_FILE" ps -q backend):/tmp/backup.tar.gz "$backup_path/container-data.tar.gz" 2>/dev/null || warn "Could not copy backup from container"
        
    elif [ -d "$DATA_DIR" ]; then
        info "Backing up from production data directory..."
        
        # Direct copy from data directory
        cp -r "$DATA_DIR"/* "$backup_path/" 2>/dev/null || warn "Could not copy from data directory"
        
    else
        # Backup Docker volumes using temporary container
        info "Backing up Docker volumes..."
        
        local volumes=$(docker volume ls -q | grep narrativehive)
        for volume in $volumes; do
            if [ -n "$volume" ]; then
                local volume_name=$(echo "$volume" | sed 's/.*_//')
                docker run --rm -v "$volume":/source -v "$backup_path":/backup alpine \
                    sh -c "cd /source && tar czf /backup/${volume_name}.tar.gz ." 2>/dev/null || warn "Could not backup volume $volume"
            fi
        done
    fi
    
    # Create backup metadata
    cat > "$backup_path/backup-info.txt" << EOF
Backup Created: $(date)
Backup Type: $([ -d "$DATA_DIR" ] && echo "Production" || echo "Development")
Project: $PROJECT_NAME
Script Version: 1.0
EOF
    
    log "✅ Backup created successfully at: $backup_path"
    
    # Show backup size
    local backup_size=$(du -sh "$backup_path" | cut -f1)
    info "Backup size: $backup_size"
}

# Restore from backup
restore_backup() {
    local backup_path="$1"
    
    if [ -z "$backup_path" ]; then
        error "Please specify backup path: ./manage-volumes.sh restore /path/to/backup"
    fi
    
    if [ ! -d "$backup_path" ]; then
        error "Backup directory not found: $backup_path"
    fi
    
    log "🔄 Restoring from backup: $backup_path"
    
    # Show backup info if available
    if [ -f "$backup_path/backup-info.txt" ]; then
        info "Backup Information:"
        cat "$backup_path/backup-info.txt"
        echo
    fi
    
    # Confirm restore
    read -p "⚠️  This will overwrite existing data. Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Restore cancelled"
        exit 0
    fi
    
    local docker_cmd=$(get_docker_compose_cmd)
    
    # Stop containers if running
    if $docker_cmd -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        warn "Stopping containers for restore..."
        $docker_cmd -f "$COMPOSE_FILE" down
    fi
    
    # Restore based on backup type
    if [ -f "$backup_path/container-data.tar.gz" ]; then
        info "Restoring container backup..."
        
        # Start temporary container to restore data
        $docker_cmd -f "$COMPOSE_FILE" up -d backend
        sleep 5
        
        # Copy backup to container and extract
        docker cp "$backup_path/container-data.tar.gz" $($docker_cmd -f "$COMPOSE_FILE" ps -q backend):/tmp/
        $docker_cmd -f "$COMPOSE_FILE" exec backend sh -c "cd /app && tar xzf /tmp/container-data.tar.gz"
        
        $docker_cmd -f "$COMPOSE_FILE" down
        
    elif [ -d "$DATA_DIR" ]; then
        info "Restoring to production data directory..."
        
        # Clear existing data
        rm -rf "$DATA_DIR"/*
        
        # Copy backup data
        cp -r "$backup_path"/* "$DATA_DIR/"
        
        # Remove backup metadata from data directory
        rm -f "$DATA_DIR/backup-info.txt"
        
        # Fix permissions
        chown -R 1000:1000 "$DATA_DIR"
        
    else
        info "Restoring to Docker volumes..."
        
        # Remove existing volumes
        local volumes=$(docker volume ls -q | grep narrativehive)
        for volume in $volumes; do
            if [ -n "$volume" ]; then
                docker volume rm "$volume" 2>/dev/null || warn "Could not remove volume $volume"
            fi
        done
        
        # Create and restore volumes
        for tar_file in "$backup_path"/*.tar.gz; do
            if [ -f "$tar_file" ]; then
                local volume_name=$(basename "$tar_file" .tar.gz)
                local full_volume_name="narrativehive_${volume_name}"
                
                docker volume create "$full_volume_name"
                docker run --rm -v "$full_volume_name":/target -v "$backup_path":/backup alpine \
                    sh -c "cd /target && tar xzf /backup/${volume_name}.tar.gz"
            fi
        done
    fi
    
    log "✅ Restore completed successfully"
    info "You can now start the containers with: ./deploy.sh --restart"
}

# Cleanup old backups
cleanup_backups() {
    local days="${1:-30}"
    
    log "🧹 Cleaning up backups older than $days days..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        info "No backup directory found"
        return
    fi
    
    local count_before=$(find "$BACKUP_DIR" -type d -name "narrativehive-backup-*" | wc -l)
    
    # Remove backups older than specified days
    find "$BACKUP_DIR" -type d -name "narrativehive-backup-*" -mtime +$days -exec rm -rf {} \; 2>/dev/null
    
    local count_after=$(find "$BACKUP_DIR" -type d -name "narrativehive-backup-*" | wc -l)
    local removed=$((count_before - count_after))
    
    log "✅ Cleanup completed. Removed $removed old backups"
    info "Remaining backups: $count_after"
}

# Show help
show_help() {
    echo "NarrativeHive Volume Management Script"
    echo
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  list                    Show volume information and sizes"
    echo "  backup                  Create a new backup"
    echo "  restore <path>          Restore from specified backup"
    echo "  cleanup [days]          Remove backups older than [days] (default: 30)"
    echo "  help                    Show this help message"
    echo
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 backup"
    echo "  $0 restore /opt/narrativehive/backups/narrativehive-backup-20240101-120000"
    echo "  $0 cleanup 7"
}

# Main function
main() {
    case "${1:-help}" in
        list|ls)
            list_volumes
            ;;
        backup|b)
            create_backup
            ;;
        restore|r)
            restore_backup "$2"
            ;;
        cleanup|clean)
            cleanup_backups "$2"
            ;;
        help|h|-h|--help)
            show_help
            ;;
        *)
            error "Unknown command: $1. Use '$0 help' for usage information."
            ;;
    esac
}

# Run main function
main "$@"
