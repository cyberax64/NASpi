from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
import psutil
import socket
import subprocess
import re
import os
import time

display_name = "Réseau"
icon = "router-fill"
bp = Blueprint('network', __name__, template_folder='templates')

HOTSPOT_PROFILE_NAME = "naspi-hotspot"

def format_bytes(byte_count):
    if byte_count is None: return "N/A"
    power = 1024; n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while byte_count >= power and n < len(power_labels):
        byte_count /= power; n += 1
    return f"{byte_count:.2f} {power_labels[n]}B"

@bp.route('/')
@login_required
def index():
    interfaces = {}
    try:
        all_addrs = psutil.net_if_addrs()
        all_stats = psutil.net_if_stats()
        net_io = psutil.net_io_counters(pernic=True)
        is_bridged = 'vmbr0' in all_addrs
        for name, addrs in all_addrs.items():
            if name == 'lo': continue
            interfaces[name] = {
                'ip_v4': 'N/A', 'netmask_v4': 'N/A', 'mac': 'N/A',
                'stats': all_stats.get(name), 'io': net_io.get(name),
                'is_bridge_slave': is_bridged and name == 'eth0'
            }
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    interfaces[name]['ip_v4'] = addr.address
                    interfaces[name]['netmask_v4'] = addr.netmask
                elif addr.family == psutil.AF_LINK:
                    interfaces[name]['mac'] = addr.address
    except Exception as e:
        flash(f"Erreur lors de la lecture des informations réseau : {e}", "danger")
    return render_template('network.html', interfaces=interfaces, format_bytes=format_bytes)

@bp.route('/static_ip/<interface_name>')
@login_required
def static_ip_form(interface_name):
    current_config = {'Address': '', 'Gateway': '', 'DNS': ''}
    config_file = f"/etc/systemd/network/10-{interface_name}.network"
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                dns_servers = []
                for line in f:
                    line = line.strip()
                    if line.lower().startswith('address='): current_config['Address'] = line.split('=', 1)[1]
                    elif line.lower().startswith('gateway='): current_config['Gateway'] = line.split('=', 1)[1]
                    elif line.lower().startswith('dns='): dns_servers.append(line.split('=', 1)[1])
                current_config['DNS'] = ' '.join(dns_servers)
    except Exception as e:
        flash(f"Impossible de lire le fichier de configuration existant : {e}", "warning")
    return render_template('static_ip.html', interface_name=interface_name, config=current_config)

@bp.route('/static_ip/<interface_name>/save', methods=['POST'])
@login_required
def static_ip_save(interface_name):
    ip = request.form.get('ip_address')
    router = request.form.get('routers')
    dns = request.form.get('domain_name_servers', '8.8.8.8 1.1.1.1')
    config_file_path = f"/etc/systemd/network/10-{interface_name}.network"
    config_content = f"[Match]\nName={interface_name}\n\n[Network]\nAddress={ip}\nGateway={router}\n"
    if dns:
        for dns_server in dns.split():
            config_content += f"DNS={dns_server}\n"
    try:
        write_command = f"echo '{config_content}' | sudo tee {config_file_path}"
        subprocess.run(write_command, shell=True, check=True)
        subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-networkd.service'], check=True)
        flash(f"Configuration IP statique pour {interface_name} appliquée.", "success")
    except Exception as e:
        flash(f"Erreur lors de la sauvegarde de la configuration : {e}", "danger")
    return redirect(url_for('network.index'))

@bp.route('/wifi/<interface_name>')
@login_required
def wifi(interface_name):
    status = {}
    networks = []
    hotspot_active = False
    try:
        result = subprocess.run(['sudo', 'nmcli', 'con', 'show', '--active'], capture_output=True, text=True, check=True)
        if HOTSPOT_PROFILE_NAME in result.stdout:
            hotspot_active = True

        status_result = subprocess.run(['sudo', 'nmcli', 'dev', 'show', interface_name], capture_output=True, text=True)
        for line in status_result.stdout.splitlines():
            if 'GENERAL.CONNECTION' in line:
                status['ssid'] = line.split(':')[1].strip() or 'Non connecté'
            if 'IP4.ADDRESS[1]' in line:
                status['ip_address'] = line.split(':')[1].strip()

        if not hotspot_active:
            list_result = subprocess.run(['sudo', 'nmcli', '--fields', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list', 'ifname', interface_name, '--rescan', 'yes'], capture_output=True, text=True)
            lines = list_result.stdout.strip().split('\n')
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = re.split(r'\s{2,}', line.strip())
                    if len(parts) >= 1:
                        networks.append({'ssid': parts[0], 'signal': parts[1] if len(parts)>1 else 'N/A', 'flags': parts[2] if len(parts)>2 else 'N/A'})

    except Exception as e:
        flash(f"Erreur de communication avec NetworkManager : {e}", "danger")

    return render_template('wifi.html', status=status, networks=networks, interface_name=interface_name, hotspot_active=hotspot_active)

@bp.route('/wifi/connect', methods=['POST'])
@login_required
def wifi_connect():
    ssid = request.form.get('ssid')
    psk = request.form.get('psk')
    interface = request.form.get('interface_name')
    try:
        cmd = ['sudo', 'nmcli', 'dev', 'wifi', 'connect', ssid, 'password', psk, 'ifname', interface]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        flash(f"Connexion au réseau Wi-Fi '{ssid}' réussie !", "success")
    except subprocess.CalledProcessError as e:
        error_message = e.stderr or e.stdout
        flash(f"Erreur lors de la connexion au Wi-Fi : {error_message}", "danger")
    return redirect(url_for('network.wifi', interface_name=interface))

@bp.route('/wifi/hotspot/enable', methods=['POST'])
@login_required
def enable_hotspot():
    interface = request.form.get('interface_name', 'wlan0')
    ssid = request.form.get('ssid')
    password = request.form.get('password')

    if not ssid or len(password) < 8:
        flash("Le SSID est requis et le mot de passe doit faire au moins 8 caractères.", "danger")
        return redirect(url_for('network.wifi', interface_name=interface))

    try:
        subprocess.run(['sudo', 'nmcli', 'con', 'down', HOTSPOT_PROFILE_NAME], capture_output=True)
        subprocess.run(['sudo', 'nmcli', 'con', 'delete', HOTSPOT_PROFILE_NAME], capture_output=True)

        cmd_create = ['sudo', 'nmcli', 'con', 'add', 'type', 'wifi', 'ifname', interface, 'con-name', HOTSPOT_PROFILE_NAME, 'autoconnect', 'yes', 'ssid', ssid]
        subprocess.run(cmd_create, check=True, capture_output=True, text=True)
        
        cmd_modify = [
            'sudo', 'nmcli', 'con', 'modify', HOTSPOT_PROFILE_NAME,
            '802-11-wireless.mode', 'ap',
            '802-11-wireless.band', 'bg',
            'wifi-sec.key-mgmt', 'wpa-psk',
            'wifi-sec.psk', password,
            'ipv4.method', 'shared',
            'ipv4.addresses', '192.168.4.1/24'
        ]
        subprocess.run(cmd_modify, check=True, capture_output=True, text=True)

        # CORRECTION : On donne une haute priorité à la connexion du hotspot
        cmd_priority = ['sudo', 'nmcli', 'con', 'modify', HOTSPOT_PROFILE_NAME, 'connection.autoconnect-priority', '100']
        subprocess.run(cmd_priority, check=True, capture_output=True, text=True)

        subprocess.run(['sudo', 'nmcli', 'con', 'up', HOTSPOT_PROFILE_NAME], check=True, capture_output=True, text=True)
        flash(f"Hotspot '{ssid}' activé et configuré pour démarrer automatiquement.", "success")

    except subprocess.CalledProcessError as e:
        error_message = e.stderr or e.stdout
        flash(f"Erreur lors de l'activation du hotspot : {error_message}", "danger")
    
    return redirect(url_for('network.wifi', interface_name=interface))

@bp.route('/wifi/hotspot/disable', methods=['POST'])
@login_required
def disable_hotspot():
    interface = request.form.get('interface_name', 'wlan0')
    try:
        subprocess.run(['sudo', 'nmcli', 'con', 'down', HOTSPOT_PROFILE_NAME], capture_output=True)
        subprocess.run(['sudo', 'nmcli', 'con', 'delete', HOTSPOT_PROFILE_NAME], capture_output=True)
        subprocess.run(['sudo', 'nmcli', 'radio', 'wifi', 'on'], check=True)
        flash("Mode Point d'Accès désactivé. Le Wi-Fi va se reconnecter à un réseau connu.", "success")
    except subprocess.CalledProcessError as e:
        error_message = e.stderr or e.stdout
        flash(f"Erreur lors de la désactivation du hotspot : {error_message}", "danger")
    return redirect(url_for('network.wifi', interface_name=interface))
