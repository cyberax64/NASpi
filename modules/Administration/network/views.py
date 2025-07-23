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
                    if line.lower().startswith('address='):
                        current_config['Address'] = line.split('=', 1)[1]
                    elif line.lower().startswith('gateway='):
                        current_config['Gateway'] = line.split('=', 1)[1]
                    elif line.lower().startswith('dns='):
                        dns_servers.append(line.split('=', 1)[1])
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
        hostapd_status = subprocess.run(['systemctl', 'is-active', 'hostapd.service'], capture_output=True, text=True)
        if hostapd_status.stdout.strip() == 'active':
            hotspot_active = True
        
        status_result = subprocess.run(['sudo', 'wpa_cli', '-i', interface_name, 'status'], capture_output=True, text=True)
        if status_result.returncode == 0:
            for line in status_result.stdout.splitlines():
                if '=' in line: key, value = line.split('=', 1); status[key] = value
        
        subprocess.run(['sudo', 'wpa_cli', '-i', interface_name, 'scan'], check=True, capture_output=True)
        time.sleep(4)
        scan_result = subprocess.run(['sudo', 'wpa_cli', '-i', interface_name, 'scan_results'], capture_output=True, text=True, check=True)
        
        lines = scan_result.stdout.splitlines()
        if len(lines) > 1:
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) >= 5:
                    networks.append({'ssid': parts[4], 'signal': parts[2], 'flags': parts[3]})
    except Exception as e:
        flash(f"Erreur de communication avec l'interface Wi-Fi : {e}", "warning")

    return render_template('wifi.html', status=status, networks=networks, interface_name=interface_name, hotspot_active=hotspot_active)

@bp.route('/wifi/connect', methods=['POST'])
@login_required
def wifi_connect():
    ssid = request.form.get('ssid')
    psk = request.form.get('psk')
    interface = request.form.get('interface_name')
    try:
        subprocess.run(['sudo', 'wpa_cli', '-i', interface, 'remove_network', 'all'], capture_output=True, text=True)
        add_result = subprocess.run(['sudo', 'wpa_cli', '-i', interface, 'add_network'], capture_output=True, text=True, check=True)
        network_id = add_result.stdout.strip()
        
        subprocess.run(['sudo', 'wpa_cli', '-i', interface, 'set_network', network_id, 'ssid', f'"{ssid}"'], check=True)
        subprocess.run(['sudo', 'wpa_cli', '-i', interface, 'set_network', network_id, 'psk', f'"{psk}"'], check=True)
        subprocess.run(['sudo', 'wpa_cli', '-i', interface, 'enable_network', network_id], check=True)
        subprocess.run(['sudo', 'wpa_cli', '-i', interface, 'save_config'], check=True)
        
        flash(f"Connexion au réseau Wi-Fi '{ssid}' en cours...", "success")
    except Exception as e:
        flash(f"Erreur lors de la connexion au Wi-Fi : {e}", "danger")
    return redirect(url_for('network.wifi', interface_name=interface))

@bp.route('/wifi/hotspot/enable', methods=['POST'])
@login_required
def enable_hotspot():
    interface = request.form.get('interface_name')
    ssid = request.form.get('ssid')
    password = request.form.get('password')
    
    if len(password) < 8:
        flash("Le mot de passe doit faire au moins 8 caractères.", "danger")
        return redirect(url_for('network.wifi', interface_name=interface))

    dnsmasq_conf = f"interface={interface}\ndhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h"
    hostapd_conf = f"interface={interface}\ndriver=nl80211\nssid={ssid}\nhw_mode=g\nchannel=7\nwmm_enabled=0\nmacaddr_acl=0\nauth_algs=1\nignore_broadcast_ssid=0\nwpa=2\nwpa_passphrase={password}\nwpa_key_mgmt=WPA-PSK\nwpa_pairwise=TKIP\nrsn_pairwise=CCMP"
    networkd_conf = f"[Match]\nName={interface}\n\n[Network]\nAddress=192.168.4.1/24\nDHCPServer=no"
    
    try:
        subprocess.run(['sudo', 'systemctl', 'stop', 'wpa_supplicant.service'], check=True)
        
        write_cmd = f"echo '{networkd_conf}' | sudo tee /etc/systemd/network/30-{interface}-hotspot.network"
        subprocess.run(write_cmd, shell=True, check=True)
        
        write_cmd = f"echo '{dnsmasq_conf}' | sudo tee /etc/dnsmasq.conf"
        subprocess.run(write_cmd, shell=True, check=True)
        
        write_cmd = f"echo '{hostapd_conf}' | sudo tee /etc/hostapd/hostapd.conf"
        subprocess.run(write_cmd, shell=True, check=True)
        
        subprocess.run("echo 'net.ipv4.ip_forward=1' | sudo tee /etc/sysctl.d/99-ip_forward.conf", shell=True, check=True)
        subprocess.run("sudo sysctl -p", shell=True, check=True)
        subprocess.run("sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE", shell=True, check=True)
        
        subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-networkd.service'], check=True)
        subprocess.run(['sudo', 'systemctl', 'unmask', 'hostapd.service'], check=True)
        subprocess.run(['sudo', 'systemctl', 'enable', 'hostapd.service'], check=True)
        subprocess.run(['sudo', 'systemctl', 'start', 'hostapd.service'], check=True)
        subprocess.run(['sudo', 'systemctl', 'start', 'dnsmasq.service'], check=True)
        
        flash(f"Mode Point d'Accès activé avec le nom de réseau '{ssid}'.", "success")
    except Exception as e:
        flash(f"Erreur lors de l'activation du hotspot : {e}", "danger")
        
    return redirect(url_for('network.wifi', interface_name=interface))

@bp.route('/wifi/hotspot/disable', methods=['POST'])
@login_required
def disable_hotspot():
    interface = request.form.get('interface_name')
    try:
        subprocess.run(['sudo', 'systemctl', 'stop', 'hostapd.service'], check=True)
        subprocess.run(['sudo', 'systemctl', 'stop', 'dnsmasq.service'], check=True)
        subprocess.run(['sudo', 'systemctl', 'disable', 'hostapd.service'], check=True)
        
        if os.path.exists(f"/etc/systemd/network/30-{interface}-hotspot.network"):
            subprocess.run(['sudo', 'rm', f"/etc/systemd/network/30-{interface}-hotspot.network"], check=True)
        
        if os.path.exists("/etc/sysctl.d/99-ip_forward.conf"):
            subprocess.run("sudo rm /etc/sysctl.d/99-ip_forward.conf", shell=True, check=True)
        subprocess.run("sudo iptables -t nat -F", shell=True, check=True)

        subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-networkd.service'], check=True)
        subprocess.run(['sudo', 'systemctl', 'start', 'wpa_supplicant.service'], check=True)
        
        flash("Mode Point d'Accès désactivé. Retour au mode Client.", "success")
    except Exception as e:
        flash(f"Erreur lors de la désactivation du hotspot : {e}", "danger")
        
    return redirect(url_for('network.wifi', interface_name=interface))
