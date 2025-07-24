import subprocess
import json
import os
import sys
import time

TASKS_FILE = '/opt/nas-panel/backup_tasks.json'

def read_tasks():
    with open(TASKS_FILE, 'r') as f:
        return json.load(f)

def write_tasks(tasks):
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=4)

def run(task_name):
    # Attend un instant pour que le fichier JSON soit mis à jour par l'interface web
    time.sleep(1) 
    
    tasks = read_tasks()
    task = tasks.get(task_name)
    if not task:
        print(f"Erreur : Tâche '{task_name}' non trouvée dans le fichier.")
        return

    destination = task['destination']
    source_path = ""
    mount_point = f"/tmp/nas_panel_mount_{task_name.replace(' ', '_')}"
    creds_file = f"/tmp/nas_panel_creds_{task_name.replace(' ', '_')}"
    
    final_status = 'Échec'
    try:
        if task['type'] == 'local':
            source_path = task['source']
        elif task['type'] == 'samba':
            s = task['source']
            remote_path = f"//{s['server']}/{s['share']}"
            os.makedirs(mount_point, exist_ok=True)
            with open(creds_file, 'w') as f:
                f.write(f"username={s['username']}\npassword={s['password']}\n")
            os.chmod(creds_file, 0o600)
            
            mount_cmd = ['sudo', 'mount', '-t', 'cifs', remote_path, mount_point, '-o', f'credentials={creds_file},iocharset=utf8,vers=3.0']
            subprocess.run(mount_cmd, check=True)
            source_path = mount_point
        
        if not source_path.endswith('/'):
            source_path += '/'
        
        command = ['sudo', 'rsync', '-a', '--delete', source_path, destination]
        subprocess.run(command, check=True, capture_output=True, text=True)
        
        final_status = 'Succès'
        
    except Exception as e:
        print(f"Erreur pendant la sauvegarde {task_name}: {e}")
    
    finally:
        if task['type'] == 'samba':
            subprocess.run(['sudo', 'umount', mount_point], capture_output=True)
            if os.path.exists(creds_file):
                os.remove(creds_file)
            if os.path.exists(mount_point):
                try:
                    os.rmdir(mount_point)
                except OSError:
                    pass

    # Mettre à jour le statut final
    current_tasks = read_tasks()
    if task_name in current_tasks:
        current_tasks[task_name]['status'] = final_status
        current_tasks[task_name]['is_running'] = False
        write_tasks(current_tasks)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        run(sys.argv[1])