#!/bin/bash

# NarrativeHive Management Script
# Quick shortcuts for common operations

PROJECT_NAME="narrativehive"

case "$1" in
    start)
        echo "🚀 Starting NarrativeHive..."
        ./deploy.sh --restart
        ;;
    stop)
        echo "🛑 Stopping NarrativeHive..."
        ./deploy.sh --stop
        ;;
    status)
        echo "📊 Checking NarrativeHive status..."
        ./deploy.sh --status
        ;;
    logs)
        echo "📋 Showing logs..."
        ./deploy.sh --logs
        ;;
    update)
        echo "🔄 Updating NarrativeHive..."
        git pull
        ./deploy.sh
        ;;
    backup)
        echo "💾 Creating backup..."
        timestamp=$(date +%Y%m%d_%H%M%S)
        mkdir -p backups
        cp -r backend/databases backups/databases_backup_$timestamp
        echo "Backup created: backups/databases_backup_$timestamp"
        ;;
    clean)
        echo "🧹 Cleaning up Docker resources..."
        ./deploy.sh --cleanup
        ;;
    *)
        echo "NarrativeHive Management Script"
        echo ""
        echo "Usage: $0 {start|stop|status|logs|update|backup|clean}"
        echo ""
        echo "Commands:"
        echo "  start   - Start/restart the application"
        echo "  stop    - Stop the application"
        echo "  status  - Show service status"
        echo "  logs    - Show container logs"
        echo "  update  - Pull latest code and redeploy"
        echo "  backup  - Backup database files"
        echo "  clean   - Clean up Docker resources"
        ;;
esac
