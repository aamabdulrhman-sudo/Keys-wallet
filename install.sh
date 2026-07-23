#!/bin/bash
clear
echo "=================================================="
echo "   Vault Secure - Installation Script"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] Run as root: sudo bash install.sh${NC}"
    exit 1
fi

INSTALL_DIR="/opt/vault-secure"
REPO_URL="https://github.com/aamabdulrhman-sudo/Keys-wallet.git"

echo -e "${CYAN}[1/7] Updating system packages...${NC}"
apt-get update -qq && apt-get upgrade -y -qq

echo -e "${CYAN}[2/7] Installing Python3 and pip...${NC}"
apt-get install -y -qq python3 python3-pip python3-venv git

echo -e "${CYAN}[3/7] Cloning project...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Project exists, updating...${NC}"
    cd "$INSTALL_DIR"
    git pull origin main
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo -e "${CYAN}[4/7] Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

echo -e "${CYAN}[5/7] Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install gunicorn -q

echo -e "${CYAN}[6/7] Setting up service...${NC}"
cat > /etc/systemd/system/vault.service << EOF
[Unit]
Description=Vault Secure - Password Manager
After=network.target

[Service]
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vault
systemctl restart vault

echo -e "${CYAN}[7/7] Checking status...${NC}"
sleep 2
if systemctl is-active --quiet vault; then
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo ""
    echo -e "${GREEN}=================================================="
    echo "   Installation Complete!"
    echo "==================================================${NC}"
    echo ""
    echo -e "${GREEN}Status: RUNNING${NC}"
    echo ""
    echo -e "Local:  ${CYAN}http://localhost:5000${NC}"
    echo -e "Network:${CYAN} http://${SERVER_IP}:5000${NC}"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo -e "  Start:   ${CYAN}sudo systemctl start vault${NC}"
    echo -e "  Stop:    ${CYAN}sudo systemctl stop vault${NC}"
    echo -e "  Restart: ${CYAN}sudo systemctl restart vault${NC}"
    echo -e "  Logs:    ${CYAN}sudo journalctl -u vault -f${NC}"
    echo -e "  Status:  ${CYAN}sudo systemctl status vault${NC}"
    echo ""
    echo -e "${GREEN}Open your browser and go to: http://${SERVER_IP}:5000${NC}"
    echo ""
else
    echo -e "${RED}[ERROR] Service failed to start. Check logs:${NC}"
    echo -e "${CYAN}sudo journalctl -u vault -n 20${NC}"
fi
