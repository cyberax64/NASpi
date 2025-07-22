# Fichier : modules/lxc/views.py

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
import subprocess
import json

display_name = "Conteneurs LXC"
icon = "grid-1x2-fill"
bp = Blueprint('lxc', __name__, template_folder='templates')

@bp.route('/')
@login_required
def index():
    containers = []
    try:
        command = ['sudo', 'lxc-ls', '--fancy', '--fancy-format', 'json']
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        raw_containers = []
        if result.stdout and result.stdout.strip():
            raw_containers = json.loads(result.stdout)
        for container in raw_containers:
            ip_address = container.get('ip', 'N/A')
            containers.append({
                'name': container.get('name'),
                'status': container.get('state'),
                'state': {'network': {'eth0': {'addresses': [{'family': 'inet', 'address': ip_address, 'netmask': '24'}]}}}
            })
    except Exception as e:
        flash(f"Erreur lors de la récupération de la liste LXC : {e}", "danger")
    return render_template('lxc.html', containers=containers)

@bp.route('/<container_name>/<action>', methods=['POST'])
@login_required
def lxc_action(container_name, action):
    action_map = {'start': 'lxc-start', 'stop': 'lxc-stop', 'restart': 'lxc-stop'}
    if action not in action_map and action != 'delete':
        flash(f"Action non valide : {action}", "warning")
        return redirect(url_for('lxc.index'))
    try:
        if action == 'delete':
            command = ['sudo', 'lxc-destroy', '-n', container_name, '-f']
        else:
            command = ['sudo', action_map[action], '-n', container_name]
        subprocess.run(command, check=True, capture_output=True, text=True)
        if action == 'restart':
            subprocess.run(['sudo', 'lxc-start', '-n', container_name, '-d'], check=True, capture_output=True, text=True)
        flash(f"Action '{action}' exécutée sur '{container_name}'.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors de l'action '{action}' sur '{container_name}': {e.stderr}", "danger")
    return redirect(url_for('lxc.index'))

@bp.route('/create')
@login_required
def create_lxc():
    templates = []
    try:
        # On retire check=True pour ne pas planter si la commande échoue
        command = ['sudo', 'lxc-ls', '-1', '--template']
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            templates = [line for line in result.stdout.splitlines() if line.strip()]
    except Exception as e:
        flash(f"Impossible de lister les templates LXC : {e}", "warning")
    return render_template('create_lxc.html', templates=templates)

@bp.route('/create/execute', methods=['POST'])
@login_required
def create_lxc_execute():
    name = request.form.get('name')
    template = request.form.get('template')
    if not name or not template:
        flash("Le nom et le template sont requis.", "danger")
        return redirect(url_for('lxc.create_lxc'))
    try:
        command = ['sudo', 'lxc-create', '-n', name, '-t', template]
        # La création peut être longue, on ne met pas de timeout
        subprocess.run(command, check=True, capture_output=True, text=True)
        flash(f"Conteneur '{name}' créé avec succès depuis le template '{template}'. Vous pouvez maintenant le démarrer.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors de la création du conteneur : {e.stderr}", "danger")
    return redirect(url_for('lxc.index'))