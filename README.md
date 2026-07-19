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

4. **Configure VPN for torrent client** (if using torrent-vpn role):
   ```bash
   # Copy the example WireGuard config file
   cp roles/torrent-vpn/files/myvpn.conf.example roles/torrent-vpn/files/myvpn.conf
   
   # Edit the WireGuard config file with your provider's details
   # You'll need:
   # - PrivateKey: Your WireGuard private key
   # - PublicKey: VPN server's public key
   # - Endpoint: VPN server IP address and port (e.g., 1.2.3.4:51820)
   # - AllowedIPs: Typically 0.0.0.0/0 to route all traffic through VPN
   
   # The file will be automatically deployed to /etc/wireguard/myvpn.conf
   ```

5. **Get Yandex Disk token** (for Immich backups):
   ```bash
   # Install rclone locally (on your control machine)
   # macOS:
   brew install rclone
   # Linux:
   sudo apt install rclone  # or use your package manager
   
   # Configure Yandex Disk remote
   rclone config
   # Follow prompts:
   # - Choose "n" for new remote
   # - Name: yandex-disk
   # - Storage: yandex
   # - Use auto config: yes (will open browser for authentication)
   # - Complete authentication in browser
   
   # Extract the token from rclone config file
   # macOS/Linux:
   cat ~/.config/rclone/rclone.conf | grep -A 2 "\[yandex-disk\]" | grep "token ="
   # Copy the entire token value (may be a JSON object or simple string)
   
   # Add the token to vault.yml:
   # yandex_disk_token: "your-token-here"
   ```

6. **Review settings** in `group_vars/all.yml`:
   - Network subnet
   - Service passwords
   - Domain names
   - Torrent VPN configuration (download paths, WebUI port)

### Deployment

**⚠️ CRITICAL: Run security hardening and firewall first!**

```bash
# Step 1: Initial security hardening and firewall (MUST BE FIRST)
ansible-playbook -i inventory.yml site.yml --tags security,firewall

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
- **Firewall**: UFW with strict deny-by-default rules (separate role)
- **Intrusion prevention**: Fail2Ban with automatic IP blocking

### Core Infrastructure  
- **Docker**: Container runtime with Docker Compose
- **Nginx Proxy Manager**: Reverse proxy with SSL automation
- **Dynamic DNS**: Automatic IP updates via myaddr.tools
- **External storage**: Automatic mounting and configuration
- **Rclone**: Cloud storage synchronization tool (used for backups)

### Monitoring & Alerting
- **Uptime Kuma**: Service monitoring dashboard with Telegram alerts
- **Glances**: System resource monitoring with web interface
- **Health checks**: Container, service, and system metric monitoring

### Services
- **Samba**: Secure file sharing (local network only)
- **Immich**: Self-hosted photo and video management (public)
- **Obsidian LiveSync**: CouchDB-based sync server for Obsidian vaults (public)
- **Vaultwarden**: Self-hosted Bitwarden-compatible password manager (public)
- **Home Assistant**: Home automation platform (public)
- **Frigate**: NVR with 3-day continuous doorbell recording (local network only)
- **qBittorrent with VPN**: Torrent client with WireGuard kill switch protection (local network only)

## 🔧 Service Access

After deployment, services are available at:

| Service | URL | Purpose |
|---------|-----|---------|
| **Nginx Proxy Manager** | `http://PI_IP:81` | Reverse proxy management |
| **Uptime Kuma** | `http://PI_IP:3001` | Monitoring dashboard |
| **Glances** | `http://PI_IP:61208` | System monitoring |
| **Samba** | `//PI_IP/shared` | File sharing |
| **Immich** | `http://PI_IP:2283` | Photo & video management |
| **Obsidian LiveSync** | `http://PI_IP:5984` | Obsidian sync server |
| **Vaultwarden** | `http://PI_IP:11011` | Password manager |
| **Home Assistant** | `http://PI_IP:8123` | Home automation |
| **Home Assistant (public)** | `https://has.yourdomain.com` | Home automation via reverse proxy |
| **Frigate** | `http://PI_IP:8971` | NVR and doorbell recordings |
| **qBittorrent** | `http://PI_IP:8234` | Torrent client WebUI (local network only) |
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
Forward to: immich-server:2283
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

### 5. Immich Setup

**Initial configuration**:
```bash
# Access locally first: http://PI_IP:2283
# Create your admin account on first access

# Upload photos via web interface or mobile app
# External storage location: /media/pi/home/immich/library

# Configure public access via Nginx Proxy Manager
# Domain: photo.yourdomain.com → immich-server:2283

# Install mobile app from:
# iOS: App Store - "Immich"
# Android: Play Store - "Immich"
```

**Backup configuration**:
- Automated backups to Yandex Disk are configured via cron (daily at 4 AM)
- Backups include database and critical folders (library, upload, profile)
- Local backups stored in `/media/pi/home/backups/immich` with 3-day retention
- To manually run backup: `/usr/local/bin/backup-immich.sh`
- View backup logs: `cat /media/pi/home/log/immich-backup-rclone.log`

### 6. Obsidian LiveSync Setup

**Initial configuration**:
```bash
# CouchDB runs on http://PI_IP:5984
# Login with credentials from vault.yml

# Setup URI is displayed after deployment - copy it to configure 
# the Obsidian LiveSync plugin in your vault

# Configure public access via Nginx Proxy Manager
# Domain: vault.yourdomain.com → obsidian_livesync_couchdb:5984
```

### 7. Vaultwarden Setup

**Initial configuration**:
```bash
# Vaultwarden runs on http://PI_IP:11011
# Access the web interface to create your admin account

# Data is stored in: /opt/stacks/vaultwarden/data

# Configure public access via Nginx Proxy Manager
# Domain: vwdn.yourdomain.com → 127.0.0.1:11011
# SSL: Request new certificate ✓
# Force SSL: ✓
# WebSocket Support: ✓ (required for real-time sync)

# Install Bitwarden clients and connect to your self-hosted instance:
# - Desktop: https://bitwarden.com/download/
# - Mobile: iOS App Store / Android Play Store - "Bitwarden"
# - Browser extensions: Available for Chrome, Firefox, Safari, Edge

# In the client, set the server URL to: https://vwdn.yourdomain.com
```

**Security Notes**:
- Signups are disabled by default (SIGNUPS_ALLOWED=false)
- Invitations are disabled by default (INVITATIONS_ALLOWED=false)
- Only create accounts manually through the admin interface
- Enable 2FA for all accounts
- Regular backups are recommended (data stored in `/opt/stacks/vaultwarden/data`)

**Backup configuration**:
- Automated backups to Yandex Disk are configured via cron (daily at 4 AM)
- Backups include the entire Vaultwarden data directory (SQLite database and attachments)
- Local backups stored in `/media/pi/home/backups/vaultwarden` with 3-day retention
- To manually run backup: `/usr/local/bin/backup-vaultwarden.sh`
- View backup logs: `cat /media/pi/home/log/vaultwarden-backup-rclone.log`

### 8. Home Assistant Setup

**Initial configuration**:
```bash
# Home Assistant runs on http://PI_IP:8123
# Public access is configured as https://has.yourdomain.com
# Access the web interface to create your administrator account

# Configuration is stored in: /opt/stacks/home-assistant/config

# The container uses host networking for local discovery integrations.
# D-Bus is mounted read-only for Bluetooth support.
# configuration.yaml is rendered from the Ansible template.
# HACS is downloaded automatically into /config/custom_components/hacs.
# The Yandex Smart Home YAML configuration exposes switch.pc and vacuum.s7.

# To validate configuration before restart:
docker exec homeassistant python -m homeassistant --script check_config --config /config
```

**MQTT broker setup**:

1. Set `mqtt_broker_username` and a strong `mqtt_broker_password` in
   `vault.yml`, then rerun the Home Assistant and firewall roles.
2. In Home Assistant, go to **Settings → Devices & services → Add integration**,
   select **MQTT**, and enter:
   - Broker: `127.0.0.1`
   - Port: `1883`
   - Username and password: the MQTT values from `vault.yml`
3. Configure LAN devices with the Raspberry Pi address on port `1883` and the
   same credentials. UFW permits this endpoint only from `network.local_subnet`.

To verify an authenticated publish without storing the password in shell
history:

```bash
read -rp 'MQTT username: ' MQTT_USERNAME
read -rsp 'MQTT password: ' MQTT_PASSWORD; echo
printf '%s %s\n%s %s\n' -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" | \
  docker exec -i mosquitto mosquitto_pub -o /dev/stdin \
  -h 127.0.0.1 -p 1883 -t manual/mqtt-test -m ok
unset MQTT_USERNAME MQTT_PASSWORD
```

**Complete HACS setup after deployment**:
1. Open Home Assistant and hard-refresh the browser page.
2. Go to **Settings → Devices & services → Add integration**.
3. Search for **HACS** and select it.
4. Accept the HACS acknowledgements and authenticate with GitHub when prompted.

**Notes**:
- Home Assistant Container does not include the Supervisor or add-ons.
- HACS is installed as a custom integration and still requires the one-time UI setup above.
- The Roborock S7 YAML mapping is managed through
  `home_assistant.yandex_smart_home` in `group_vars/all.yml`.
- PC control uses HASS.Agent Satellite MQTT availability as its state source.
  Configure the Satellite service to publish to the broker and create its
  graceful shutdown command before deploying this configuration.
- The managed PC inputs under `home_assistant.yandex_smart_home.pc` are:
  - Availability topic: `homeassistant/sensor/TV-satellite/availability`
  - Startup button: `button.media_pc_power_switch_pc_power_button`
  - Shutdown button: `button.tv_satellite_shutdown`
- `switch.pc` reports on while HASS.Agent Satellite is online or during its
  15-second startup window. Satellite, network, and MQTT failures are therefore
  indistinguishable from a powered-off PC.
- Yandex Smart Home is not installed by this playbook. Install it manually,
  rerun the Home Assistant role so it detects the component and renders the
  YAML configuration, then add the integration in
  **Settings → Devices & services** and select the YAML entity filter.
- A GitHub account is required to complete HACS authentication.
- The default timezone is `system.timezone` from `group_vars/all.yml`.
- Nginx Proxy Manager creates `has.<ddns_domain>` and forwards it to `127.0.0.1:8123` with WebSocket support.

### 9. Frigate Setup

**Initial configuration**:
```bash
# Frigate runs on http://PI_IP:8971
# Doorbell recordings are stored in: /media/pi/home/frigate/recordings
# The Calex RTSP stream is configured through frigate_doorbell_rtsp_url in vault.yml

# Frigate records the doorbell stream continuously and keeps the last 3 days.
# To change retention, update frigate.retention_days in group_vars/all.yml.
```

**Notes**:
- Frigate uses the RTSP stream directly and does not depend on Tuya doorbell events.
- The first visit to the Frigate UI creates or displays the initial login flow depending on the Frigate image version.
- Continuous recording requires the RTSP stream to remain reachable from the Raspberry Pi.

### 10. Torrent VPN Setup

**Initial configuration**:
```bash
# qBittorrent WebUI is available at http://PI_IP:8234
# Default credentials: admin / adminadmin
# ⚠️ IMPORTANT: Change password on first login!

# Verify VPN connection:
sudo systemctl status wg-quick@myvpn

# Check WireGuard interface:
ip addr show myvpn
# or
wg show myvpn

# Verify kill switch is working:
# - qBittorrent should only bind to WireGuard interface (myvpn)
# - Firewall rules prevent traffic outside VPN
# - If VPN disconnects, torrent traffic is blocked

# Download location: /media/pi/home/samba/shared/downloads
# Incomplete downloads: /media/pi/home/torrents/incomplete
```

**VPN Configuration**:
- WireGuard config is located at `/etc/wireguard/myvpn.conf`
- VPN service runs as `wg-quick@myvpn`
- The playbook automatically configures firewall rules to:
  - Allow WireGuard server connection (outgoing UDP, port from config)
  - Allow DNS resolution (outgoing)
  - Block all other outgoing traffic when VPN is active (kill switch)
  - Allow qBittorrent WebUI access from local network only

**Port Forwarding for Torrent Speed**:
If you use a custom WireGuard server (e.g., wg-easy), you need to forward the torrent listening port on the VPN server to improve download speeds. Without this, peers cannot connect to you directly.

On your WireGuard server host, run:
```bash
# Replace <PI_WG_IP> with the Pi's WireGuard tunnel IP
# Find it with: docker exec gluetun ip addr
iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 6881 -j DNAT --to-destination <PI_WG_IP>:6881
iptables -t nat -A PREROUTING -i eth0 -p udp --dport 6881 -j DNAT --to-destination <PI_WG_IP>:6881
iptables -A FORWARD -p tcp --dport 6881 -j ACCEPT
iptables -A FORWARD -p udp --dport 6881 -j ACCEPT

# Make persistent across reboots
apt install iptables-persistent
netfilter-persistent save
```

**Troubleshooting**:
```bash
# Check VPN connection status
sudo journalctl -u wg-quick@myvpn -f

# Verify WireGuard interface status
wg show myvpn

# Verify qBittorrent is bound to VPN interface
docker exec qbittorrent ip addr show

# Test VPN connectivity
ping -I myvpn 8.8.8.8

# Check firewall rules
sudo ufw status numbered | grep -E "(WireGuard|DNS|8234)"
```

## 🛠️ Selective Deployment

Deploy specific components using tags:

```bash
# Security hardening only (run first!)
ansible-playbook -i inventory.yml site.yml --tags security

# Firewall configuration (run after security hardening)
ansible-playbook -i inventory.yml site.yml --tags firewall

# Core infrastructure
ansible-playbook -i inventory.yml site.yml --tags docker,nginx

# Monitoring services
ansible-playbook -i inventory.yml site.yml --tags kuma,glances

# Home automation
ansible-playbook -i inventory.yml site.yml --tags home-assistant

# Home automation with public proxy registration
ansible-playbook -i inventory.yml site.yml --tags home-assistant,nginx

# Doorbell NVR
ansible-playbook -i inventory.yml site.yml --tags frigate,firewall

# File services
ansible-playbook -i inventory.yml site.yml --tags samba

# Photo & video management
ansible-playbook -i inventory.yml site.yml --tags immich

# Rclone installation and configuration (required for immich and vaultwarden backups)
ansible-playbook -i inventory.yml site.yml --tags rclone

# Note: Immich backups are automatically configured when running the immich role
# if yandex_disk_token is set in vault.yml

# Obsidian sync server
ansible-playbook -i inventory.yml site.yml --tags obsidian

# Password manager
ansible-playbook -i inventory.yml site.yml --tags vaultwarden

# Note: Vaultwarden backups are automatically configured when running the vaultwarden role
# if yandex_disk_token is set in vault.yml

# Torrent client with VPN (requires VPN config file)
ansible-playbook -i inventory.yml site.yml --tags torrent

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
| Immich | 2283 | Local only | Photo & video management |
| Nginx Proxy Manager | 81 | Local only | Reverse proxy management |
| Uptime Kuma | 3001 | Local only | Monitoring dashboard |
| Glances | 61208 | Local only | System monitoring |
| Vaultwarden | 11011 | Local only | Password manager |
| Home Assistant | 8123 | Local only | Direct port; public access goes through HTTPS reverse proxy |
| Frigate | 8971 | Local only | NVR and doorbell recordings |
| qBittorrent WebUI | 8234 | Local only | Torrent client management |
| WireGuard | Dynamic (UDP) | VPN server | VPN connection (outgoing) |
| DNS | 53/udp | Any | DNS resolution (outgoing) |

### Security Hardening
- ✅ Default user removal
- ✅ Key-based SSH authentication only
- ✅ Custom SSH port
- ✅ Fail2Ban intrusion prevention
- ✅ UFW firewall with deny-by-default
- ✅ Regular security updates
- ✅ Service isolation via Docker networks
- ✅ WireGuard VPN kill switch for torrent traffic (prevents leaks if VPN disconnects)

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
