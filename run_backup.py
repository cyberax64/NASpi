import subprocess
import json
import os
import re
import sys

TASKS_FILE = '/opt/nas-panel/backup_tasks.json'
LOG_DIR = '/tmp/nas_panel_logs'
os.makedirs(LOG_DIR, exist_ok=True)

def read_tasks():
    with open(TASKS_FILE, 'r') as f:
        return json.load(f)

def write_tasks(tasks):
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=4)

def run(task_name):
    tasks = read_tasks()
    task = tasks[task_name]
    
    log_file_path = os.path.join(LOG_DIR, f"backup_{task_name.replace(' ', '_')}.log")
    
    source_path = ""
    mount_point = f"/tmp/nas_panel_mount_{task_name.replace(' ', '_')}"
    creds_file = f"/tmp/nas_panel_creds_{task_name.replace(' ', '_')}"

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
        
        if not source_path.endswith('/'): source_path += '/'
        
        command = ['sudo', 'rsync', '-a', '--delete', '--info=progress2', source_path, task['destination']]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        for line in iter(process.stdout.readline, ''):
            with open(log_file_path, 'a') as log_f:
                log_f.write(line)
            
            match = re.search(r'(\d+)%', line)
            if match:
                current_tasks = read_tasks()
                current_tasks[task_name]['progress'] = int(match.group(1))
                write_tasks(current_tasks)
        
        process.stdout.close()
        return_code = process.wait()

        final_status = 'Succès' if return_code == 0 else 'Échec'
        
    except Exception as e:
        final_status = 'Échec'
        with open(log_file_path, 'a') as log_f:
            log_f.write(f"\n--- ERREUR SCRIPT ---\n{e}")
    
    finally:
        if task['type'] == 'samba':
            subprocess.run(['sudo', 'umount', mount_point], capture_output=True)
            if os.path.exists(creds_file): os.remove(creds_file)
            if os.path.exists(mount_point):
                try: os.rmdir(mount_point)
                except OSError: pass

    final_tasks = read_tasks()
    final_tasks[task_name]['is_running'] = False
    final_tasks[task_name]['status'] = final_status
    write_tasks(final_tasks)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        task_name_arg = sys.argv[1]
        run(task_name_arg)