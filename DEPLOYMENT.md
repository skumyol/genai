# NarrativeHive Deployment Guide

Complete deployment guide for NarrativeHive on Alpine Linux with Docker containers.

## Quick Start

```bash
# Clone repository
git clone https://github.com/skumyol/genai.git
cd genai

# Deploy in development mode
./deploy.sh

# Deploy in production mode with persistent volumes
./deploy.sh --prod

# Deploy with backup
./deploy.sh --prod --backup
```

## Architecture

```
Internet → nginx (443/80) → Docker Containers
                              ├── Frontend (port 5176)
                              └── Backend (port 5002)
```

### Services

- **Frontend**: React + TypeScript + Vite (nginx container)
- **Backend**: Python Flask API
- **Proxy**: System nginx with SSL termination
- **Data**: Persistent volumes for databases, metrics, static files

## Prerequisites

### System Requirements
- Alpine Linux
- Docker and Docker Compose
- nginx (already running)
- SSL certificates (via Certbot)
- Git

### Ports Used
- `5176`: Frontend container
- `5002`: Backend container
- `443/80`: nginx proxy (public)

## Installation

### 1. Install Docker
```bash
apk add docker docker-compose
rc-service docker start
rc-update add docker
```

### 2. Verify nginx and SSL
```bash
# Check nginx is running
pgrep nginx

# Verify SSL certificate exists
ls /etc/letsencrypt/live/narrativehive.skumyol.com/
```

### 3. Clone and Deploy
```bash
cd /root
git clone https://github.com/skumyol/genai.git
cd genai
chmod +x deploy.sh manage-volumes.sh
./deploy.sh --prod
```

## Deployment Options

### Development Mode
```bash
./deploy.sh
```
- Uses `docker-compose.yml`
- Data stored in Docker volumes
- Suitable for testing

### Production Mode
```bash
./deploy.sh --prod
```
- Uses `docker-compose.prod.yml`
- Data persisted to `/opt/narrativehive/data/`
- Automatic backups available
- Health checks enabled

### Available Deployment Flags
```bash
./deploy.sh --help
```

| Flag | Description |
|------|-------------|
| `--prod` | Production mode with persistent volumes |
| `--backup` | Create backup before deployment |
| `--restore <path>` | Restore from backup |
| `--build-only` | Only build images |
| `--stop` | Stop containers |
| `--restart` | Restart containers |
| `--logs` | Show container logs |
| `--status` | Show container status |

## Volume Management

### Backup Operations
```bash
# List volumes and backups
./manage-volumes.sh list

# Create backup
./manage-volumes.sh backup

# Restore from backup
./manage-volumes.sh restore /opt/narrativehive/backups/backup-folder

# Clean old backups (30+ days)
./manage-volumes.sh cleanup
```

### Production Data Locations
```
/opt/narrativehive/
├── data/
│   ├── databases/          # SQLite files
│   ├── metrics/           # Analytics data
│   │   └── deep_analysis/ # Detailed metrics
│   ├── static/            # Static assets
│   │   └── avatars/       # Generated avatars
│   └── logs/              # Application logs
└── backups/               # Automated backups
```

## Configuration Files

### docker-compose.yml (Development)
- Regular Docker volumes
- Basic health checks
- Development settings

### docker-compose.prod.yml (Production)
- Bind mounts to `/opt/narrativehive/data/`
- Enhanced health checks
- Production optimizations
- Resource limits

### nginx.conf (Container)
- Internal container nginx configuration
- API proxy to backend
- Static file serving
- CORS headers

## Monitoring

### Health Checks
```bash
# Application health
curl https://narrativehive.skumyol.com/api/health

# Container status
./deploy.sh --status

# View logs
./deploy.sh --logs
```

### Log Locations

**Production Mode:**
- App logs: `/opt/narrativehive/data/logs/`
- nginx: `/var/log/nginx/`
- Docker: `docker logs [container-name]`

**Development Mode:**
- All logs via: `docker logs [container-name]`

## GitHub Actions Integration

See [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) for complete CI/CD setup.

### Quick Setup
1. Add repository secrets (HOST, USERNAME, PRIVATE_KEY, PORT)
2. Push to main branch
3. Automated deployment triggers

## Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs
docker logs narrativehive-backend
docker logs narrativehive-frontend

# Check port conflicts
netstat -tlnp | grep -E ':(5002|5176)'
```

**nginx configuration errors:**
```bash
# Test configuration
nginx -t

# Check current config
cat /etc/nginx/http.d/narrativehive.skumyol.com.conf
```

**Volume/data issues:**
```bash
# Check volume usage
./manage-volumes.sh list

# Check permissions (production)
ls -la /opt/narrativehive/data/
```

**SSL/HTTPS issues:**
```bash
# Check certificate
openssl x509 -in /etc/letsencrypt/live/narrativehive.skumyol.com/fullchain.pem -text -noout

# Renew certificate
certbot renew
```

### Debug Commands

```bash
# Full container info
docker ps -a
docker inspect narrativehive-backend

# System resources
df -h
free -h
docker system df

# Network connectivity
curl -I https://narrativehive.skumyol.com
curl -I http://localhost:5176
curl -I http://localhost:5002/api/health
```

## Maintenance

### Regular Tasks

**Weekly:**
```bash
# Update system packages
apk update && apk upgrade

# Clean Docker resources
docker system prune -f

# Check logs for errors
./deploy.sh --logs | grep -i error
```

**Monthly:**
```bash
# Clean old backups
./manage-volumes.sh cleanup

# Update SSL certificates
certbot renew

# Review disk usage
./manage-volumes.sh list
```

### Updates

**Application Updates:**
```bash
cd /root/genai
git pull origin main
./deploy.sh --prod --backup
```

**System Updates:**
```bash
apk update && apk upgrade
systemctl restart docker
./deploy.sh --restart
```

## Security

### Firewall Configuration
```bash
# Install and configure UFW or use iptables
apk add ufw
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
ufw enable
```

### Backup Security
- Store backups in secure location
- Consider encrypting sensitive backups
- Regular backup testing

### Container Security
- Keep base images updated
- Review and limit container permissions
- Monitor for security updates

## Performance Optimization

### Resource Monitoring
```bash
# Container resource usage
docker stats

# System resources
htop
iotop
```

### Optimization Tips
1. **Database**: Regular SQLite optimization
2. **Static Files**: Use nginx caching
3. **Images**: Optimize Docker image sizes
4. **Logs**: Implement log rotation

## Support

### Getting Help
1. Check this documentation
2. Review application logs
3. Check GitHub Issues
4. Monitor system resources

### Reporting Issues
Include:
- Deployment command used
- Error messages
- System information (`uname -a`, `docker version`)
- Log excerpts

## Development

### Local Development
```bash
# Frontend development
npm run dev

# Backend development
cd backend
python app.py
```

### Building Custom Images
```bash
# Build specific service
docker build -f Dockerfile.backend -t custom-backend .
docker build -f Dockerfile.frontend -t custom-frontend .
```

---

## Quick Reference

### Essential Commands
```bash
# Deploy production
./deploy.sh --prod

# Stop all services
./deploy.sh --stop

# View status
./deploy.sh --status

# Create backup
./manage-volumes.sh backup

# View logs
./deploy.sh --logs
```

### Important Paths
- Application: `/root/genai/`
- Data: `/opt/narrativehive/data/`
- Backups: `/opt/narrativehive/backups/`
- nginx config: `/etc/nginx/http.d/narrativehive.skumyol.com.conf`
- SSL certs: `/etc/letsencrypt/live/narrativehive.skumyol.com/`