from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
import subprocess
import json
import os
import re

display_name = "Sauvegardes"
icon = "arrow-repeat"
bp = Blueprint('backups', __name__, template_folder='templates')

TASKS_FILE = '/opt/nas-panel/backup_tasks.json'

def read_tasks():
    if not os.path.exists(TASKS_FILE): return {}
    try:
        with open(TASKS_FILE, 'r') as f: return json.load(f)
    except (json.JSONDecodeError, IOError): return {}

def write_tasks(tasks):
    with open(TASKS_FILE, 'w') as f: json.dump(tasks, f, indent=4)

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        name = request.form.get('name')
        task_type = request.form.get('task_type')
        destination = request.form.get('destination')
        
        if not all([name, task_type, destination]):
            flash("Tous les champs sont requis.", "danger")
        else:
            tasks = read_tasks()
            if name in tasks:
                flash(f"Une tâche nommée '{name}' existe déjà.", "warning")
            else:
                task_data = {'type': task_type, 'destination': destination, 'status': 'Jamais exécutée', 'is_running': False}
                if task_type == 'local':
                    task_data['source'] = request.form.get('source_local')
                elif task_type == 'samba':
                    task_data['source'] = {
                        'server': request.form.get('source_samba_server'),
                        'share': request.form.get('source_samba_share'),
                        'username': request.form.get('source_samba_user'),
                        'password': request.form.get('source_samba_pass')
                    }
                tasks[name] = task_data
                write_tasks(tasks)
                flash(f"Tâche de sauvegarde '{name}' créée.", "success")
        
        return redirect(url_for('backups.index'))

    tasks = read_tasks()
    return render_template('backups.html', tasks=tasks)

@bp.route('/delete/<task_name>', methods=['POST'])
@login_required
def delete_task(task_name):
    tasks = read_tasks()
    if task_name in tasks:
        tasks.pop(task_name)
        write_tasks(tasks)
        flash(f"Tâche '{task_name}' supprimée.", "success")
    return redirect(url_for('backups.index'))

@bp.route('/run/<task_name>', methods=['POST'])
@login_required
def run_task(task_name):
    tasks = read_tasks()
    if task_name not in tasks:
        flash("Tâche introuvable.", "danger")
        return redirect(url_for('backups.index'))
    
    if tasks[task_name].get('is_running', False):
        flash("Cette tâche est déjà en cours d'exécution.", "warning")
        return redirect(url_for('backups.index'))

    # CORRECTION : On remonte de 3 niveaux pour trouver le script à la racine
    script_path = os.path.join(os.path.dirname(__file__), 'run_backup.py')
    subprocess.Popen(['python3', script_path, task_name])

    tasks[task_name]['status'] = 'En cours...'
    tasks[task_name]['is_running'] = True
    write_tasks(tasks)

    flash(f"Lancement de la sauvegarde '{task_name}' en arrière-plan.", "info")
    return redirect(url_for('backups.index'))