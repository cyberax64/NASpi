from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
import subprocess
import json
import psutil
import time
import re

display_name = "Gestion des Disques"
icon = "hdd-fill"
bp = Blueprint('disks', __name__, template_folder='templates')

def get_disk_info():
    try:
        command = ['lsblk', '-J', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,LABEL,MODEL,UUID']
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        all_devices = data.get('blockdevices', [])
        processed_devices = []
        raid_arrays = {}

        def find_raid_arrays(devices):
            for device in devices:
                if 'raid' in device.get('type', ''):
                    if device['name'] not in raid_arrays:
                        raid_arrays[device['name']] = device
                if 'children' in device:
                    find_raid_arrays(device['children'])
        
        find_raid_arrays(all_devices)

        for device in all_devices:
            if device.get('type') == 'disk':
                if 'children' in device:
                    device['children'] = [child for child in device['children'] if 'raid' not in child.get('type', '')]
                processed_devices.append(device)
        
        for raid_name, raid_data in raid_arrays.items():
            processed_devices.append(raid_data)
            
        return processed_devices

    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        flash(f"Erreur lors de la récupération des informations disque : {e}", "danger")
        return []

def get_usage(mountpoint):
    if not mountpoint: return None
    try: return psutil.disk_usage(mountpoint)
    except FileNotFoundError: return None

def get_uuid(partition_path):
    try:
        command = ['sudo', 'blkid', '-s', 'UUID', '-o', 'value', partition_path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def remove_fstab_entry(device_path):
    try:
        uuid = get_uuid(device_path)
        if uuid:
            delete_fstab_command = ['sudo', 'sed', '-i', f'/{uuid}/d', '/etc/fstab']
            subprocess.run(delete_fstab_command, check=True)
            flash(f"Entrée pour le périphérique {device_path} (UUID: {uuid}) supprimée de /etc/fstab.", "info")
    except Exception as e:
        flash(f"Avertissement : n'a pas pu supprimer l'entrée de fstab pour {device_path}. Erreur : {e}", "warning")

def get_free_space(disk_name):
    try:
        device_path = f"/dev/{disk_name}"
        command = ['sudo', 'parted', device_path, 'unit', 'B', 'print', 'free']
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        free_line = [line for line in lines if "Free Space" in line]
        if free_line:
            parts = free_line[-1].strip().split()
            start_bytes = int(parts[0].replace('B', ''))
            size_bytes = int(parts[2].replace('B', ''))
            return {'start': start_bytes, 'size': size_bytes}
    except Exception:
        return None
    return None

@bp.route('/')
@login_required
def index():
    raw_disks = get_disk_info()
    processed_disks = []
    
    active_raid_members = set()
    try:
        with open('/proc/mdstat', 'r') as f:
            content = f.read()
        found_devices = re.findall(r'(\w+)\[\d+\]', content)
        active_raid_members.update(found_devices)
    except FileNotFoundError:
        pass

    for disk in raw_disks:
        disk['has_mounted_children'] = False
        if 'children' in disk:
            for part in disk['children']:
                part['usage'] = get_usage(part.get('mountpoint'))
                if part.get('mountpoint'):
                    disk['has_mounted_children'] = True
                if part['name'] in active_raid_members:
                    part['is_active_raid_member'] = True
        else:
            disk['usage'] = get_usage(disk.get('mountpoint'))
        processed_disks.append(disk)
            
    return render_template('disks.html', disks=processed_disks)

@bp.route('/partition/<disk_name>')
@login_required
def partition_disk(disk_name):
    disk_size_bytes = 0
    try:
        result = subprocess.run(['lsblk', '-b', '-no', 'SIZE', f'/dev/{disk_name}'], capture_output=True, text=True, check=True)
        disk_size_bytes = int(result.stdout.strip())
    except Exception:
        pass
    return render_template('partition_disk.html', disk_name=disk_name, disk_size_gb=disk_size_bytes / (1024**3))

@bp.route('/partition/<disk_name>/execute', methods=['POST'])
@login_required
def partition_disk_execute(disk_name):
    confirmation = request.form.get('disk_name_confirm', '').strip()
    if confirmation != disk_name:
        flash("Le nom du disque de confirmation ne correspond pas. Opération annulée.", "warning")
        return redirect(url_for('disks.index'))

    partitions_def = []
    for i in range(1, 10):
        size = request.form.get(f'part_size_{i}')
        unit = request.form.get(f'part_unit_{i}')
        fstype = request.form.get(f'part_fstype_{i}')
        if size:
            partitions_def.append({'size': size, 'unit': unit, 'fstype': fstype})

    if not partitions_def:
        flash("Aucune partition n'a été définie. Opération annulée.", "warning")
        return redirect(url_for('disks.index'))
    
    device_path = f"/dev/{disk_name}"
    try:
        remove_fstab_entry(device_path)
        result = subprocess.run(['sudo', 'parted', device_path, 'unit', 'MB', 'print'], capture_output=True, text=True, check=True)
        match = re.search(r'Disk .*: ([\d\.]+)MB', result.stdout)
        total_size_mb = float(match.group(1))

        subprocess.run(['sudo', 'parted', device_path, '--script', '--', 'mklabel', 'gpt'], check=True)
        flash(f"Table de partition GPT créée sur {device_path}.", "success")
        time.sleep(2)

        current_pos_mb = 1.0
        for i, part in enumerate(partitions_def):
            part_num = i + 1
            size = float(part['size'])
            unit = part['unit']
            fstype = part['fstype']
            
            size_mb = 0
            if unit == 'GB': size_mb = size * 1024
            elif unit == 'TB': size_mb = size * 1024 * 1024
            elif unit == '%': size_mb = (total_size_mb / 100.0) * size
            else: size_mb = size

            start_mb = current_pos_mb
            end_mb = current_pos_mb + size_mb

            if end_mb > total_size_mb + 1:
                flash(f"La taille des partitions dépasse la taille du disque.", "danger")
                return redirect(url_for('disks.partition_disk', disk_name=disk_name))

            command = ['sudo', 'parted', '-a', 'optimal', device_path, '--script', '--', 'mkpart', f'primary', '', f'{start_mb}MB', f'{end_mb}MB']
            subprocess.run(command, check=True)
            flash(f"Partition #{part_num} créée.", "success")
            
            current_pos_mb = end_mb
            
            subprocess.run(['sudo', 'partprobe', device_path], check=True)
            time.sleep(2)
            
            new_partition_path = f"{device_path}{part_num}"
            
            if fstype == 'raid':
                subprocess.run(['sudo', 'parted', device_path, 'set', str(part_num), 'raid', 'on'], check=True)
                subprocess.run(['sudo', 'dd', 'if=/dev/zero', 'bs=1M', 'count=100', f'of={new_partition_path}'], check=True)
                flash(f"Flag RAID activé pour la partition {new_partition_path}.", "success")
            elif fstype == 'ext4':
                subprocess.run(['sudo', 'mkfs.ext4', '-F', new_partition_path], check=True)
                flash(f"Partition {new_partition_path} formatée en ext4.", "success")
            elif fstype == 'btrfs':
                subprocess.run(['sudo', 'mkfs.btrfs', '-f', new_partition_path], check=True)
                flash(f"Partition {new_partition_path} formatée en btrfs.", "success")
            elif fstype == 'xfs':
                subprocess.run(['sudo', 'mkfs.xfs', '-f', new_partition_path], check=True)
                flash(f"Partition {new_partition_path} formatée en xfs.", "success")
            elif fstype == 'linux-swap':
                subprocess.run(['sudo', 'mkswap', new_partition_path], check=True)
                flash(f"Partition {new_partition_path} configurée en SWAP.", "success")

        flash(f"Toutes les opérations sur {device_path} sont terminées.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Une erreur critique est survenue : {e.stderr or e.stdout or e}", "danger")

    return redirect(url_for('disks.index'))

@bp.route('/mount/<partition_name>')
@login_required
def mount_partition_confirm(partition_name):
    uuid = get_uuid(f"/dev/{partition_name}")
    if not uuid:
        flash(f"Impossible de trouver l'UUID pour {partition_name}. Impossible de continuer.", "danger")
        return redirect(url_for('disks.index'))
    return render_template('mount_partition.html', partition_name=partition_name, uuid=uuid)

@bp.route('/mount/<partition_name>/execute', methods=['POST'])
@login_required
def mount_partition_execute(partition_name):
    mount_name = request.form.get('mount_name')
    uuid = request.form.get('uuid')
    if not re.match(r'^[a-zA-Z0-9_-]+$', mount_name):
        flash("Le nom du point de montage est invalide.", "danger")
        return redirect(url_for('disks.mount_partition_confirm', partition_name=partition_name))
    
    mount_path = f"/mnt/{mount_name}"
    
    with open('/etc/fstab', 'r') as f:
        fstab_content = f.read()
    if uuid in fstab_content or mount_path in fstab_content:
        flash(f"Une entrée pour ce disque ou ce point de montage existe déjà dans /etc/fstab.", "warning")
        return redirect(url_for('disks.index'))

    try:
        fstab_line = f"UUID={uuid}  {mount_path}  ext4  defaults,auto,users,rw,nofail  0  0\n"
        subprocess.run(['sudo', 'mkdir', '-p', mount_path], check=True)
        add_fstab_command = f"echo '{fstab_line}' | sudo tee -a /etc/fstab"
        subprocess.run(add_fstab_command, shell=True, check=True)
        
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
        subprocess.run(['sudo', 'mount', '-a'], check=True)
        
        flash(f"Partition {partition_name} montée avec succès sur {mount_path} !", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Une erreur est survenue lors du montage : {e}", "danger")
        
    return redirect(url_for('disks.index'))

@bp.route('/unmount/<partition_name>', methods=['POST'])
@login_required
def unmount_partition_execute(partition_name):
    device_path = f"/dev/{partition_name}"
    mountpoint = None
    for part in psutil.disk_partitions():
        if part.device == device_path:
            mountpoint = part.mountpoint
            break
    if mountpoint in ['/', '/boot/firmware']:
        flash(f"Démontage de la partition système '{mountpoint}' interdit par sécurité.", "danger")
        return redirect(url_for('disks.index'))
    if not mountpoint:
        flash(f"La partition {partition_name} n'est pas montée.", "warning")
        return redirect(url_for('disks.index'))
    try:
        subprocess.run(['sudo', 'umount', device_path], check=True)
        delete_fstab_command = ['sudo', 'sed', '-i', f'\\|{mountpoint}|d', '/etc/fstab']
        subprocess.run(delete_fstab_command, check=True)
        flash(f"Partition {partition_name} démontée de {mountpoint} et ligne supprimée de /etc/fstab.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Une erreur est survenue lors du démontage : {e}", "danger")
    return redirect(url_for('disks.index'))

@bp.route('/format/<partition_name>')
@login_required
def format_partition_confirm(partition_name):
    return render_template('format_partition.html', partition_name=partition_name)

@bp.route('/format/<partition_name>/execute', methods=['POST'])
@login_required
def format_partition_execute(partition_name):
    confirmation = request.form.get('partition_name_confirm', '').strip()
    if confirmation != partition_name:
        flash("Le nom de la partition de confirmation ne correspond pas. Opération annulée.", "warning")
        return redirect(url_for('disks.index'))
    device_path = f"/dev/{partition_name}"
    for part in psutil.disk_partitions():
        if part.device == device_path:
            flash(f"Impossible de formater une partition montée ({part.mountpoint}). Veuillez la démonter d'abord.", "danger")
            return redirect(url_for('disks.index'))
    try:
        remove_fstab_entry(device_path)
        subprocess.run(['sudo', 'mkfs.ext4', '-F', device_path], check=True)
        flash(f"Partition {device_path} formatée avec succès en ext4.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Une erreur est survenue lors du formatage : {e}", "danger")
    return redirect(url_for('disks.index'))

@bp.route('/wipe/<disk_name>')
@login_required
def wipe_disk_confirm(disk_name):
    return render_template('wipe_disk.html', disk_name=disk_name)

@bp.route('/wipe/<disk_name>/execute', methods=['POST'])
@login_required
def wipe_disk_execute(disk_name):
    confirmation = request.form.get('disk_name_confirm', '').strip()
    if confirmation != disk_name:
        flash("Le nom du disque de confirmation ne correspond pas. Opération annulée.", "warning")
        return redirect(url_for('disks.index'))
    device_path = f"/dev/{disk_name}"
    for part in psutil.disk_partitions():
        if part.device.startswith(device_path):
            flash(f"Impossible d'effacer le disque car une de ses partitions ({part.device}) est montée sur {part.mountpoint}. Veuillez la démonter d'abord.", "danger")
            return redirect(url_for('disks.index'))
    try:
        for i in range(1, 10):
            remove_fstab_entry(f"{device_path}{i}")
        subprocess.run(['sudo', 'wipefs', '--all', device_path], check=True)
        flash(f"Toutes les signatures de système de fichiers et de partition ont été effacées de {device_path}. Le disque est maintenant brut.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Une erreur est survenue lors de l'effacement du disque : {e}", "danger")
    return redirect(url_for('disks.index'))

@bp.route('/delete_partition/<partition_name>')
@login_required
def delete_partition_confirm(partition_name):
    return render_template('delete_partition.html', partition_name=partition_name)

@bp.route('/delete_partition/<partition_name>/execute', methods=['POST'])
@login_required
def delete_partition_execute(partition_name):
    confirmation = request.form.get('partition_name_confirm', '').strip()
    if confirmation != partition_name:
        flash("Le nom de la partition de confirmation ne correspond pas. Opération annulée.", "warning")
        return redirect(url_for('disks.index'))

    device_path = f"/dev/{partition_name}"
    
    for part in psutil.disk_partitions():
        if part.device == device_path:
            flash(f"Impossible de supprimer une partition montée ({part.mountpoint}). Veuillez la démonter d'abord.", "danger")
            return redirect(url_for('disks.index'))

    try:
        # CORRECTION : Utilise une expression régulière plus robuste pour extraire le nom du disque et le numéro
        match = re.match(r'^(.*?)(p)?(\d+)$', partition_name)
        if not match:
            flash(f"Impossible d'analyser le nom de la partition : {partition_name}", "danger")
            return redirect(url_for('disks.index'))

        disk_name = match.group(1)   # Ex: 'sda' ou 'md0'
        part_number = match.group(3) # Ex: '1'

        remove_fstab_entry(device_path)
        
        command = ['sudo', 'parted', f'/dev/{disk_name}', '--script', '--', 'rm', part_number]
        subprocess.run(command, check=True)

        flash(f"Partition {partition_name} supprimée avec succès.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Une erreur est survenue lors de la suppression de la partition : {e.stderr or e.stdout or e}", "danger")

    return redirect(url_for('disks.index'))

@bp.route('/add_partition/<disk_name>')
@login_required
def add_partition_confirm(disk_name):
    free_space = get_free_space(disk_name)
    if not free_space:
        flash("Aucun espace libre détecté sur ce disque.", "warning")
        return redirect(url_for('disks.index'))
    return render_template('add_partition.html', disk_name=disk_name, free_space=free_space)

@bp.route('/add_partition/<disk_name>/execute', methods=['POST'])
@login_required
def add_partition_execute(disk_name):
    confirmation = request.form.get('disk_name_confirm', '').strip()
    if confirmation != disk_name:
        flash("Le nom du disque de confirmation ne correspond pas. Opération annulée.", "warning")
        return redirect(url_for('disks.index'))

    size = float(request.form.get('part_size'))
    unit = request.form.get('part_unit')
    start_bytes = int(request.form.get('start_bytes'))
    
    device_path = f"/dev/{disk_name}"
    
    size_bytes = 0
    if unit == 'GB': size_bytes = size * (1024**3)
    elif unit == 'MB': size_bytes = size * (1024**2)
    elif unit == 'TB': size_bytes = size * (1024**4)
    
    end_bytes = start_bytes + size_bytes

    try:
        command = ['sudo', 'parted', '-a', 'optimal', device_path, '--script', '--', 'mkpart', 'primary', 'ext4', f'{start_bytes}B', f'{end_bytes}B']
        subprocess.run(command, check=True)
        subprocess.run(['sudo', 'partprobe', device_path], check=True)
        flash(f"Nouvelle partition de {size}{unit} créée avec succès sur {disk_name}.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Une erreur est survenue lors de la création de la partition : {e}", "danger")

    return redirect(url_for('disks.index'))