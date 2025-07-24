# Fichier : modules/wireguard/views.py

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
import subprocess
import os
import re
from werkzeug.utils import secure_filename

display_name = "VPN (WireGuard)"
icon = "shield-lock-fill"
bp = Blueprint('wireguard', __name__, template_folder='templates')

WG_CONF_PATH = '/etc/wireguard/'

def get_wg_status():
    status = {}
    try:
        result = subprocess.run(['sudo', 'wg', 'show'], capture_output=True, text=True)
        current_interface = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith('interface:'):
                current_interface = line.split(':')[1].strip()
                status[current_interface] = {'name': current_interface, 'peer': 'N/A', 'transfer': 'N/A'}
            elif line.startswith('peer:') and current_interface:
                status[current_interface]['peer'] = line.split(':')[1].strip()
            elif line.startswith('transfer:') and current_interface:
                status[current_interface]['transfer'] = line.split(':')[1].strip()
    except Exception:
        pass
    return status

def get_available_configs():
    configs = []
    try:
        files = os.listdir(WG_CONF_PATH)
        conf_files = sorted([f for f in files if f.endswith('.conf')])
        for f_name in conf_files:
            conf_data = {'name': f_name.replace('.conf', ''), 'original_name': 'N/A'}
            try:
                with open(os.path.join(WG_CONF_PATH, f_name), 'r') as f:
                    first_line = f.readline()
                    if '# Original Filename:' in first_line:
                        conf_data['original_name'] = first_line.split(':', 1)[1].strip()
            except Exception:
                pass
            configs.append(conf_data)
    except FileNotFoundError:
        flash(f"Le dossier {WG_CONF_PATH} n'existe pas.", "danger")
    return configs

@bp.route('/')
@login_required
def index():
    active_status = get_wg_status()
    available_configs = get_available_configs()
    return render_template('wireguard.html', status=active_status, configs=available_configs)

@bp.route('/up/<conf_name>', methods=['POST'])
@login_required
def wg_up(conf_name):
    try:
        subprocess.run(['sudo', 'wg-quick', 'up', conf_name], check=True, capture_output=True, text=True)
        # On active le service pour le démarrage automatique
        subprocess.run(['sudo', 'systemctl', 'enable', f'wg-quick@{conf_name}.service'], check=True, capture_output=True, text=True)
        flash(f"Connexion '{conf_name}' activée et configurée pour démarrer automatiquement.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors de l'activation de '{conf_name}': {e.stderr}", "danger")
    return redirect(url_for('wireguard.index'))

@bp.route('/down/<conf_name>', methods=['POST'])
@login_required
def wg_down(conf_name):
    try:
        subprocess.run(['sudo', 'wg-quick', 'down', conf_name], check=True, capture_output=True, text=True)
        # On désactive le service du démarrage automatique
        subprocess.run(['sudo', 'systemctl', 'disable', f'wg-quick@{conf_name}.service'], check=True, capture_output=True, text=True)
        flash(f"Connexion '{conf_name}' désactivée et retirée du démarrage automatique.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors de la désactivation de '{conf_name}': {e.stderr}", "danger")
    return redirect(url_for('wireguard.index'))

@bp.route('/upload', methods=['POST'])
@login_required
def upload_config():
    if 'config_file' not in request.files:
        flash("Aucun fichier sélectionné.", "warning")
        return redirect(url_for('wireguard.index'))
    file = request.files['config_file']
    if file.filename == '':
        flash("Aucun fichier sélectionné.", "warning")
        return redirect(url_for('wireguard.index'))
        
    if file and file.filename.endswith('.conf'):
        original_filename = secure_filename(file.filename)
        i = 0
        while True:
            new_name = f"wg{i}"
            new_filename = f"{new_name}.conf"
            if not os.path.exists(os.path.join(WG_CONF_PATH, new_filename)):
                break
            i += 1
        
        original_content = file.read().decode('utf-8')
        new_content = f"# Original Filename: {original_filename}\n\n{original_content}"
        temp_path = f"/tmp/{new_filename}"
        with open(temp_path, 'w') as f:
            f.write(new_content)
        
        subprocess.run(['sudo', 'mv', temp_path, os.path.join(WG_CONF_PATH, new_filename)])
        flash(f"Fichier '{original_filename}' importé sous le nom '{new_filename}'.", "success")
    else:
        flash("Fichier invalide. Seuls les fichiers .conf sont autorisés.", "warning")
    return redirect(url_for('wireguard.index'))

@bp.route('/delete/<conf_name>', methods=['POST'])
@login_required
def delete_config(conf_name):
    file_path = os.path.join(WG_CONF_PATH, f"{conf_name}.conf")
    try:
        if os.path.exists(file_path):
            # On s'assure que le service est arrêté et désactivé avant de supprimer
            subprocess.run(['sudo', 'wg-quick', 'down', conf_name], capture_output=True)
            subprocess.run(['sudo', 'systemctl', 'disable', f'wg-quick@{conf_name}.service'], capture_output=True)
            subprocess.run(['sudo', 'rm', file_path], check=True)
            flash(f"Configuration '{conf_name}' supprimée.", "success")
        else:
            flash("Fichier de configuration introuvable.", "warning")
    except Exception as e:
        flash(f"Erreur lors de la suppression du fichier : {e}", "danger")
    return redirect(url_for('wireguard.index'))