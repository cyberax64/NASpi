#!/bin/bash

# Script d'installation pour le NAS Panel

# Couleurs pour les messages
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
RESET=$(tput sgr0)

echo "${GREEN}--- Début de l'installation du NAS Panel ---${RESET}"

# === Vérification des droits root ===
if [ "$EUID" -ne 0 ]; then
  echo "${YELLOW}Veuillez lancer ce script en tant que root ou avec sudo.${RESET}"
  exit 1
fi

# === Étape 1: Installation des dépendances système ===
echo "${GREEN}--> Étape 1/6 : Installation des dépendances système (apt)...${RESET}"
apt-get update
apt-get install -y samba mdadm docker.io git rsync ufw gunicorn openresolv wireguard-tools gpsd gpsd-clients
apt remove --purge -y exim4 avahi-daemon libavahi-core7 libdaemon0 libnss-mdns rpicam-apps-lite
systemctl stop dnsmasq
systemctl disable dnsmasq
SAMBA_CONF="/etc/samba/smb.conf"
PRIMARY_INTERFACE=$(ip -4 route ls | grep default | grep -Po '(?<=dev )(\S+)' | head -n1)
sed -i '/^ *interfaces/d' "$SAMBA_CONF"
sed -i '/^ *bind interfaces only/d' "$SAMBA_CONF
sed -i "/\[global\]/a \interfaces = 0.0.0.0" "$SAMBA_CONF"
echo "console=serial0,115200 console=tty1 root=PARTUUID=35890969-02 rootfstype=ext4 fsck.repair=yes rootwait cfg80211.ieee80211_regdom=FR ipv6.disable=1" > /boot/firmware/cmdline.txt


# === Étape 2: Copie des fichiers de l'application ===
echo "${GREEN}--> Étape 2/6 : Copie des fichiers de l'application vers /opt/nas-panel...${RESET}"
# Récupère le répertoire où se trouve le script
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
DEST_DIR="/opt/nas-panel"

mkdir -p "$DEST_DIR"
# Copie tout sauf le script d'installation lui-même
rsync -av --exclude 'install.sh' "$SCRIPT_DIR/" "$DEST_DIR/"

# === Étape 3: Installation des dépendances Python ===
echo "${GREEN}--> Étape 3/6 : Installation des dépendances Python (pip)...${RESET}"
apt-get install -y python3-psutil python3-flask python3-flask-sqlalchemy python3-flask-login python3-docker python3-flask-socketio python3-gunicorn python3-eventlet python3-gps

# === Étape 4: Configuration du Cron pour le collecteur de stats ===
echo "${GREEN}--> Étape 4/6 : Configuration de la tâche planifiée (cron)...${RESET}"
CRON_JOB="* * * * * /usr/bin/python3 $DEST_DIR/collector.py >> $DEST_DIR/collector.log 2>&1"
# Ajoute la tâche seulement si elle n'existe pas déjà
(crontab -l 2>/dev/null | grep -Fq "$CRON_JOB") || (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

# === Étape 5: Configuration du Pare-feu (UFW) ===
echo "${GREEN}--> Étape 5/6 : Configuration du pare-feu (UFW)...${RESET}"
# Ajoute la règle pour notre application
ufw allow 5001/tcp comment 'NAS Panel Web UI'
# Ajoute la règle pour le SSH
ufw allow ssh
# Ajoute la règle pour le Samba
ufw allow samba
# Active le pare-feu sans demander de confirmation
# Autorise les requêtes DHCP (attribution d'IP)
sudo ufw allow in on wlan0 to any port 67 proto udp

# Autorise les requêtes DNS (traduction des noms de domaine)
sudo ufw allow in on wlan0 to any port 53
ufw --force enable

# === Étape 6: Création et activation du service systemd ===
echo "${GREEN}--> Étape 6/6 : Création du service de l'application...${RESET}"
cp "$DEST_DIR/nas-panel.service" "/etc/systemd/system/nas-panel.service"
systemctl daemon-reload
systemctl enable nas-panel.service
systemctl start nas-panel.service

echo "usb_max_current_enable=1" >> /boot/firmware/config.txt

echo "${GREEN}--- Installation terminée ! ---${RESET}"
echo "L'application NAS Panel est maintenant installée dans ${YELLOW}$DEST_DIR${RESET}"
echo "Le service est démarré. Vous pouvez vérifier son statut avec : ${YELLOW}systemctl status nas-panel${RESET}"
echo "Pour voir les logs de l'application, utilisez : ${YELLOW}journalctl -u nas-panel -f${RESET}"
reboot
