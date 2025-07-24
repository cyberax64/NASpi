from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
from main import socketio # On importe socketio
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
        
        tasks = read_tasks()
        if name in tasks:
            flash(f"Une tâche nommée '{name}' existe déjà.", "warning")
        else:
            task_data = {'type': task_type, 'destination': destination, 'status': 'Jamais exécutée'}
            if task_type == 'local':
                task_data['source'] = request.form.get('source_local')
            elif task_type == 'samba':
                task_data['source'] = {
                    'server': request.form.get('source_samba_server'), 'share': request.form.get('source_samba_share'),
                    'username': request.form.get('source_samba_user'), 'password': request.form.get('source_samba_pass')
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

@socketio.on('run_backup_task', namespace='/backups')
def run_backup_task(data):
    task_name = data['name']
    tasks = read_tasks()
    if task_name not in tasks:
        socketio.emit('backup_log', {'log': f"Erreur: Tâche '{task_name}' introuvable."}, namespace='/backups')
        return

    task = tasks[task_name]
    destination = task['destination']
    
    source_path, mount_point, creds_file = "", None, None
    
    try:
        if task['type'] == 'local':
            source_path = task['source']
        elif task['type'] == 'samba':
            s = task['source']
            remote_path = f"//{s['server']}/{s['share']}"
            mount_point = f"/tmp/nas_panel_mount_{task_name.replace(' ', '_')}"
            creds_file = f"/tmp/nas_panel_creds_{task_name.replace(' ', '_')}"
            
            os.makedirs(mount_point, exist_ok=True)
            with open(creds_file, 'w') as f: f.write(f"username={s['username']}\npassword={s['password']}\n")
            os.chmod(creds_file, 0o600)
            
            mount_cmd = ['sudo', 'mount', '-t', 'cifs', remote_path, mount_point, '-o', f'credentials={creds_file},iocharset=utf8,vers=3.0']
            subprocess.run(mount_cmd, check=True, capture_output=True, text=True)
            source_path = mount_point
        
        if not source_path.endswith('/'): source_path += '/'

        command = ['sudo', 'rsync', '-a', '--delete', '--progress', source_path, destination]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1)

        for line in iter(process.stdout.readline, ''):
            socketio.emit('backup_log', {'log': line}, namespace='/backups')
            if match := re.search(r'\s+(\d+)%\s+', line):
                socketio.emit('backup_progress', {'percent': int(match.group(1))}, namespace='/backups')
        
        process.stdout.close()
        return_code = process.wait()
        
        status_msg = 'Succès' if return_code == 0 else 'Échec'
        socketio.emit('backup_log', {'log': f'\n--- SAUVEGARDE TERMINÉE : {status_msg} ---'}, namespace='/backups')
    
    except Exception as e:
        socketio.emit('backup_log', {'log': f'\n--- ERREUR CRITIQUE : {e} ---'}, namespace='/backups')
    
    finally:
        if mount_point:
            subprocess.run(['sudo', 'umount', mount_point], capture_output=True)
            if creds_file and os.path.exists(creds_file): os.remove(creds_file)
            if os.path.exists(mount_point):
                try: os.rmdir(mount_point)
                except OSError: pass