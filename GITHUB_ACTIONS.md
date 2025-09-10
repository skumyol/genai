# GitHub Actions Integration for NarrativeHive

This document explains how to set up automated deployment for NarrativeHive using GitHub Actions.

## Overview

The GitHub Actions workflows provide:
- **Continuous Integration**: Automated testing on pull requests
- **Automated Deployment**: Deploy to production on main branch pushes
- **Container Registry**: Store Docker images in GitHub Container Registry

## Setup Instructions

### 1. Repository Secrets

Configure the following secrets in your GitHub repository (`Settings` → `Secrets and variables` → `Actions`):

#### Server Access
- `HOST`: Your server IP address or domain (e.g., `skumyol.com`)
- `USERNAME`: SSH username (usually `root` for Alpine Linux)
- `PRIVATE_KEY`: SSH private key content
- `PORT`: SSH port (default: `22`)

#### Optional Secrets
- `GITHUB_TOKEN`: Automatically provided by GitHub (no setup needed)

### 2. Server Prerequisites

Ensure your server has:
```bash
# Docker and Docker Compose
apk add docker docker-compose
rc-service docker start
rc-update add docker

# Git (for pulling latest code)
apk add git

# Basic utilities
apk add curl wget
```

### 3. Directory Structure

The deployment expects this structure on your server:
```
/root/genai/genai/          # Your repository
/opt/narrativehive/         # Production data
├── data/                   # Persistent volumes
│   ├── databases/
│   ├── metrics/
│   ├── static/
│   └── logs/
└── backups/               # Automatic backups
```

## Workflows

### CI Workflow (`.github/workflows/ci.yml`)

**Triggered by**: Pull requests and pushes to `main`/`develop`

**Actions**:
1. Install Node.js and Python dependencies
2. Build frontend and test backend imports
3. Build Docker images
4. Test container health

### Deployment Workflow (`.github/workflows/deploy.yml`)

**Triggered by**: Pushes to `main` branch only

**Actions**:
1. Run CI tests
2. Build and push Docker images to GitHub Container Registry
3. SSH to server and deploy latest images

## Manual Deployment

You can also trigger deployment manually:

1. Go to `Actions` tab in your repository
2. Select "Deploy to Production" workflow
3. Click "Run workflow" button
4. Select branch (usually `main`)

## Local Development vs Production

### Development Mode
```bash
# Uses regular docker-compose.yml
# Volumes are managed by Docker
./deploy.sh

# Check status
./deploy.sh --status

# View logs
./deploy.sh --logs
```

### Production Mode
```bash
# Uses docker-compose.prod.yml
# Data persisted to /opt/narrativehive/data
./deploy.sh --prod

# Backup before deployment
./deploy.sh --prod --backup

# Restore from backup
./deploy.sh --prod --restore /opt/narrativehive/backups/backup-folder
```

## Volume Management

Use the volume management script:

```bash
# Show volume information
./manage-volumes.sh list

# Create backup
./manage-volumes.sh backup

# Restore from backup
./manage-volumes.sh restore /opt/narrativehive/backups/narrativehive-backup-YYYYMMDD-HHMMSS

# Cleanup old backups (older than 30 days)
./manage-volumes.sh cleanup

# Cleanup old backups (older than 7 days)
./manage-volumes.sh cleanup 7
```

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   - Verify `HOST`, `USERNAME`, `PORT` secrets
   - Ensure SSH key has correct permissions
   - Test SSH connection manually

2. **Docker Build Failed**
   - Check if Docker is running on server
   - Verify disk space availability
   - Check for port conflicts

3. **Deployment Failed**
   - Check nginx configuration
   - Verify SSL certificates exist
   - Check port availability (5002, 5176)

### Debug Commands

```bash
# Check container status
docker ps -a

# View container logs
docker logs narrativehive-backend
docker logs narrativehive-frontend

# Check nginx status
systemctl status nginx

# Test nginx configuration
nginx -t

# Check port usage
netstat -tlnp | grep -E ':(5002|5176|80|443)'
```

### Health Checks

The application provides health endpoints:
- Backend: `https://narrativehive.skumyol.com/api/health`
- Frontend: `https://narrativehive.skumyol.com/`

## Monitoring

### Log Locations

**Development:**
- Container logs: `docker logs [container-name]`

**Production:**
- Application logs: `/opt/narrativehive/data/logs/`
- Nginx logs: `/var/log/nginx/`
- System logs: `/var/log/messages`

### Backup Strategy

**Automatic backups** are created:
- Before each deployment (if `--backup` flag used)
- Manually with `./manage-volumes.sh backup`

**Backup contents:**
- Database files (SQLite)
- Metrics data
- Static files (avatars, etc.)
- Application logs

### Monitoring Commands

```bash
# Check deployment status
./deploy.sh --status

# Monitor logs in real-time
./deploy.sh --logs

# Check volume usage
./manage-volumes.sh list

# Check system resources
df -h
free -h
docker system df
```

## Security Considerations

1. **Secrets Management**: Never commit secrets to repository
2. **SSH Access**: Use key-based authentication, disable password auth
3. **Firewall**: Only open necessary ports (80, 443, 22)
4. **Updates**: Keep Alpine Linux and Docker updated
5. **Backups**: Store backups securely, consider encryption

## Advanced Configuration

### Custom Environment Variables

Add to `docker-compose.prod.yml`:
```yaml
environment:
  - API_PORT=5002
  - PYTHONUNBUFFERED=1
  - NODE_ENV=production
  - CUSTOM_VAR=value
```

### Resource Limits

Add to service definitions:
```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
    reservations:
      memory: 256M
      cpus: '0.25'
```

### Additional Services

Add monitoring, database backups, or other services:
```yaml
services:
  # ... existing services ...
  
  monitoring:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
```

## Migration Guide

### From Manual Deployment to GitHub Actions

1. Set up repository secrets (see step 1 above)
2. Push your code to GitHub
3. Verify CI workflow passes
4. Merge to main branch to trigger deployment
5. Monitor deployment in Actions tab

### Data Migration

To migrate existing data:
```bash
# Backup current data
./manage-volumes.sh backup

# Deploy with new configuration
./deploy.sh --prod

# If needed, restore data
./manage-volumes.sh restore /path/to/backup
```
