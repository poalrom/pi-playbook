# Raspberry Pi Home Server Ansible Playbook

**Automated deployment of a secure, observable, and versatile home server on Raspberry Pi**

This Ansible playbook implements the complete architecture described in the comprehensive security guide, transforming a fresh Raspberry Pi into a hardened home server with reverse proxy, monitoring, file sharing, and containerized services.

## 🎯 Purpose

This playbook automates the deployment of a security-first home server architecture featuring:

- **Layered Security**: Host hardening, firewall, intrusion prevention, and reverse proxy
- **Service Isolation**: Docker containerization with dedicated networks
- **Centralized Monitoring**: Real-time service health monitoring with Telegram alerts  
- **Public & Local Services**: Secure internet-facing services alongside local-only file sharing
- **SSL Automation**: Automatic certificate management via Let's Encrypt

All internet traffic is funneled through a single, secure entry point (reverse proxy), while maintaining strict firewall rules and comprehensive monitoring.

## 🚀 Quick Start

### Prerequisites

1. **Fresh Raspberry Pi OS** (Lite 64-bit recommended)
2. **SSH access** with default `pi` user
3. **Ansible** installed on your control machine
4. **SSH key pair** generated (`ssh-keygen`)

### Installation

```bash
# Install Ansible (choose your platform)
brew install ansible                    # macOS
sudo apt install ansible              # Ubuntu/Debian
pip3 install ansible                  # Others

# Clone this repository
git clone <repository-url>
cd pi-playbook
```

### Configuration

1. **Update inventory.yml** with your Pi's IP address:
   ```yaml
   ansible_host: 192.168.178.112  # Change to your Pi's IP
   ```

2. **⚠️ IMPORTANT**: Change SSH port from 22 to custom port:
   ```yaml
   # In inventory.yml - initially use port 22
   ansible_ssh_port: 22
   
   # In group_vars/all.yml - set your custom port
   ssh:
     port: 2312  # Change to your desired port
   ```

3. **Configure sensitive data** in `vault.yml`:
   ```bash
   cp vault-template.yml vault.yml
   ansible-vault edit vault.yml
   ```

4. **Review settings** in `group_vars/all.yml`:
   - Network subnet
   - Service passwords
   - Domain names

### Deployment

**⚠️ CRITICAL: Run security hardening first!**

```bash
# Step 1: Initial security hardening (MUST BE FIRST)
ansible-playbook -i inventory.yml site.yml --tags security

# Step 2: Update inventory to use custom SSH port
# Edit inventory.yml and change ansible_ssh_port from 22 to 2312

# Step 3: Deploy remaining services
ansible-playbook -i inventory.yml site.yml
```

## 📋 What Gets Deployed

### Security Foundation
- **System hardening**: Updates, secure configuration
- **User management**: New admin user, removal of default `pi` user
- **SSH security**: Key-based auth, custom port, password auth disabled
- **Firewall**: UFW with strict deny-by-default rules
- **Intrusion prevention**: Fail2Ban with automatic IP blocking

### Core Infrastructure  
- **Docker**: Container runtime with Docker Compose
- **Nginx Proxy Manager**: Reverse proxy with SSL automation
- **Dynamic DNS**: Automatic IP updates via myaddr.tools
- **External storage**: Automatic mounting and configuration

### Monitoring & Alerting
- **Uptime Kuma**: Service monitoring dashboard with Telegram alerts
- **Glances**: System resource monitoring with web interface
- **Health checks**: Container, service, and system metric monitoring

### Services
- **Samba**: Secure file sharing (local network only)
- **PhotoPrism**: AI-powered photo management (optional, public)

## 🔧 Service Access

After deployment, services are available at:

| Service | URL | Purpose |
|---------|-----|---------|
| **Nginx Proxy Manager** | `http://PI_IP:81` | Reverse proxy management |
| **Uptime Kuma** | `http://PI_IP:3001` | Monitoring dashboard |
| **Glances** | `http://PI_IP:61208` | System monitoring |
| **Samba** | `//PI_IP/shared` | File sharing |
| **PhotoPrism** | `http://PI_IP:2342` | Photo management |
| **SSH** | `ssh -p 2312 home-pi@PI_IP` | Secure shell access |

## 🔄 Post-Deployment Steps

### 1. Router Configuration
Configure port forwarding to enable public access:
```bash
# Forward these ports from your router to the Pi's IP
External Port 80  → PI_IP:80   (HTTP)
External Port 443 → PI_IP:443  (HTTPS)
```

### 2. SSL Certificate Setup

In Nginx Proxy Manager (`http://PI_IP:81`):
1. Add **Proxy Hosts** for your services
2. Configure **SSL certificates** with Let's Encrypt
3. Enable **Force SSL** and **HTTP/2**

Example configuration:
```
Domain: photo.yourdomain.com
Forward to: photoprism:2342
SSL: Request new certificate ✓
Force SSL: ✓
```

### 3. Monitoring Configuration

**Setup Uptime Kuma** (`http://PI_IP:3001`):
1. Create admin account
2. **Configure Telegram bot**:
   ```bash
   # In Telegram, message @BotFather:
   /newbot
   # Follow prompts, save the API token
   ```
3. **Add monitors** for each service:
   - HTTP monitors for web services
   - TCP monitors for network services
   - Docker container monitors
   - System resource monitors


### 4. Samba File Server Setup

**Configure network access**:
```bash
# Samba should already be configured and running
# Test access from other devices:

# Windows: \\PI_IP\shared
# macOS: smb://PI_IP/shared  
# Linux: smbclient //PI_IP/shared -U home-pi

# Set Samba password (if needed)
sudo smbpasswd -a home-pi
```

### 5. PhotoPrism Setup

**Initial configuration**:
```bash
# Access locally first: http://PI_IP:2342
# Login with credentials from vault.yml

# Upload photos to external storage
cp -r /path/to/photos/* /media/pi/home/photoprism/originals/

# Configure public access via Nginx Proxy Manager
# Domain: photo.yourdomain.com → photoprism:2342
```

## 🛠️ Selective Deployment

Deploy specific components using tags:

```bash
# Security hardening only (run first!)
ansible-playbook -i inventory.yml site.yml --tags security

# Core infrastructure
ansible-playbook -i inventory.yml site.yml --tags docker,nginx

# Monitoring services
ansible-playbook -i inventory.yml site.yml --tags kuma,glances

# File services
ansible-playbook -i inventory.yml site.yml --tags samba

# Photo management
ansible-playbook -i inventory.yml site.yml --tags photoprism

# Dynamic DNS
ansible-playbook -i inventory.yml site.yml --tags ddns
```

## 🔒 Security Features

### Firewall Rules Applied
| Service | Port | Source | Purpose |
|---------|------|--------|---------|
| SSH | 2312 | Local only | Secure administration |
| HTTP | 80 | Internet | Reverse proxy entry |
| HTTPS | 443 | Internet | Secure web traffic |
| Samba | 137,138,139,445 | Local only | File sharing |

### Security Hardening
- ✅ Default user removal
- ✅ Key-based SSH authentication only
- ✅ Custom SSH port
- ✅ Fail2Ban intrusion prevention
- ✅ UFW firewall with deny-by-default
- ✅ Regular security updates
- ✅ Service isolation via Docker networks

## 🔧 Maintenance & Troubleshooting

### Service Management
```bash
# Check service status
sudo systemctl status ssh fail2ban
docker ps

# Check logs
sudo journalctl -u ssh
sudo journalctl -u fail2ban
docker logs <container-name>

# Update Docker services
cd /opt/stacks/<service>
docker compose pull
docker compose up -d

# System updates
sudo apt update && sudo apt upgrade -y
```

### Common Issues
```bash
# SSH connection issues
ssh -p 2312 -vvv home-pi@PI_IP

# Firewall status
sudo ufw status verbose

# Service connectivity
nmap -p 80,443,2312 PI_IP

# Disk space
df -h
```

