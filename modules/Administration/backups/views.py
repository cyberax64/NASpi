# Fichier : modules/Administration/backups/views.py

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
import subprocess
import json
import os

display_name = "Sauvegardes"
icon = "arrow-repeat"
bp = Blueprint('backups', __name__, template_folder='templates')

TASKS_FILE = '/opt/nas-panel/backup_tasks.json'

def read_tasks():
    """Lit les tâches de sauvegarde depuis le fichier JSON."""
    if not os.path.exists(TASKS_FILE):
        return {}
    try:
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def write_tasks(tasks):
    """Écrit les tâches dans le fichier JSON."""
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=4)

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST': # Gère la création d'une nouvelle tâche
        name = request.form.get('name')
        source = request.form.get('source')
        destination = request.form.get('destination')
        
        if not name or not source or not destination:
            flash("Tous les champs sont requis.", "danger")
            return redirect(url_for('backups.index'))

        tasks = read_tasks()
        if name in tasks:
            flash(f"Une tâche nommée '{name}' existe déjà.", "warning")
        else:
            tasks[name] = {'source': source, 'destination': destination, 'status': 'Jamais exécutée'}
            write_tasks(tasks)
            flash(f"Tâche de sauvegarde '{name}' créée avec succès.", "success")
        
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

    task = tasks[task_name]
    source = task['source']
    destination = task['destination']
    
    # On s'assure que le dossier source se termine par un / pour copier le contenu
    if not source.endswith('/'):
        source += '/'

    try:
        flash(f"Lancement de la sauvegarde '{task_name}'...", "info")
        # Commande rsync : -a (archive), -v (verbeux), --delete (supprime les fichiers en trop dans la dest)
        command = ['sudo', 'rsync', '-av', '--delete', source, destination]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        
        tasks[task_name]['status'] = 'Succès'
        tasks[task_name]['log'] = result.stdout
        write_tasks(tasks)
        
        flash(f"Sauvegarde '{task_name}' terminée avec succès.", "success")
    except subprocess.CalledProcessError as e:
        tasks[task_name]['status'] = 'Échec'
        tasks[task_name]['log'] = e.stderr
        write_tasks(tasks)
        flash(f"Erreur lors de la sauvegarde '{task_name}': {e.stderr}", "danger")
    
    return redirect(url_for('backups.index'))