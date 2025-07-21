# Fichier : modules/raid/views.py

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
import re
import subprocess
import json

display_name = "Gestion RAID"
icon = "hdd-rack-fill"
bp = Blueprint('raid', __name__, template_folder='templates')

def get_raid_details(device_name):
    try:
        command = ['sudo', 'mdadm', '--detail', f'/dev/{device_name}']
        result = subprocess.run(command, capture_output=True, text=True)
        details = {'name': device_name, 'level': 'N/A', 'state': 'inconnu', 'devices': [], 'action': None, 'progress': None}
        if result.returncode != 0:
            if "No such file or directory" in result.stderr: details['state'] = 'inactive'
            elif "does not appear to be an md device" in result.stderr: details['state'] = 'broken'
            return details
        output = result.stdout
        if match := re.search(r'Raid Level : (raid\d+)', output): details['level'] = match.group(1)
        if match := re.search(r'State : ([\w\s,]+)', output): details['state'] = match.group(1).strip()
        if match := re.search(r'Resync Status : (\d+)% complete', output):
            details.update({'action': 'resync', 'progress': float(match.group(1))})
        if match := re.search(r'Rebuild Status : (\d+)% complete', output):
            details.update({'action': 'rebuild', 'progress': float(match.group(1))})
        details['devices'] = [match.group(1) for line in output.splitlines() if (match := re.search(r'\d+\s+\d+\s+\d+\s+\d+\s+[\w\s]+\s+(/dev/\S+)', line))]
        return details
    except Exception:
        return {'name': device_name, 'level': 'N/A', 'state': 'erreur de lecture', 'devices': []}

def discover_all_arrays():
    arrays = {}
    try:
        command = ['sudo', 'mdadm', '--examine', '--scan']
        result = subprocess.run(command, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if line.startswith('ARRAY'):
                if match := re.search(r'/dev/(md\d+|md/\w+)', line):
                    name = match.group(1).replace('md/', 'md')
                    if name not in arrays: arrays[name] = get_raid_details(name)
    except Exception:
        pass
    return arrays

def find_raid_candidates():
    clean_candidates, unclean_candidates, active_members = [], [], set()
    try:
        with open('/proc/mdstat', 'r') as f: active_members.update(re.findall(r'(\w+)\[\d+\]', f.read()))
    except FileNotFoundError: pass
    try:
        result = subprocess.run(['lsblk', '-J', '-o', 'NAME,TYPE,MOUNTPOINT,SIZE'], capture_output=True, text=True, check=True)
        all_devices = json.loads(result.stdout).get('blockdevices', [])
        def flatten(devices):
            flat_list = []
            for dev in devices:
                if dev.get('type') == 'part': flat_list.append(dev)
                if 'children' in dev: flat_list.extend(flatten(dev['children']))
            return flat_list
        for part in flatten(all_devices):
            if not part.get('mountpoint') and part['name'] not in active_members:
                examine = subprocess.run(['sudo', 'mdadm', '--examine', f"/dev/{part['name']}"], capture_output=True, text=True)
                data = {'name': part['name'], 'size': part['size']}
                if 'No md superblock detected' in examine.stderr: clean_candidates.append(data)
                elif 'md superblock exists' in examine.stdout: unclean_candidates.append(data)
    except Exception as e:
        flash(f"Erreur lors de la recherche de candidats RAID : {e}", "danger")
    return clean_candidates, unclean_candidates

@bp.route('/')
@login_required
def index():
    raid_arrays = discover_all_arrays()
    return render_template('raid.html', raid_arrays=raid_arrays)

@bp.route('/create')
@login_required
def create_raid():
    clean_candidates, unclean_candidates = find_raid_candidates()
    return render_template('create_raid.html', clean_candidates=clean_candidates, unclean_candidates=unclean_candidates)

@bp.route('/create/execute', methods=['POST'])
@login_required
def create_raid_execute():
    level = request.form.get('level')
    devices = request.form.getlist('devices')
    reqs = {'raid0': 2, 'raid1': 2, 'raid5': 3, 'raid6': 4}
    min_dev = reqs.get(level)
    if not min_dev or len(devices) < min_dev:
        flash(f"Le {level} requiert au moins {min_dev} disques. Sélectionnés: {len(devices)}.", "danger")
        return redirect(url_for('raid.create_raid'))
    num = 0
    while f"md{num}" in discover_all_arrays(): num += 1
    md_device = f"/dev/md{num}"
    paths = [f"/dev/{dev}" for dev in devices]
    command = ['sudo', 'mdadm', '--create', md_device, '--level', level.replace('raid', ''), '--raid-devices', str(len(devices)), *paths, '--run']
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        flash(f"Grappe RAID {md_device} créée avec succès !", "success")
        return redirect(url_for('raid.index'))
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors de la création de la grappe RAID : {e.stderr}", "danger")
        return redirect(url_for('raid.create_raid'))

@bp.route('/zero_superblock/<partition_name>', methods=['POST'])
@login_required
def zero_superblock(partition_name):
    try:
        subprocess.run(['sudo', 'mdadm', '--zero-superblock', f"/dev/{partition_name}"], check=True)
        flash(f"Superblock de {partition_name} nettoyé.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors du nettoyage du superblock de {partition_name}: {e}", "danger")
    return redirect(url_for('raid.create_raid'))

@bp.route('/destroy/<array_name>')
@login_required
def destroy_raid_confirm(array_name):
    return render_template('destroy_raid.html', array_name=array_name)

@bp.route('/destroy/<array_name>/execute', methods=['POST'])
@login_required
def destroy_raid_execute(array_name):
    confirmation = request.form.get('array_name_confirm', '').strip()
    if confirmation != array_name:
        flash("Le nom de la grappe de confirmation ne correspond pas. Opération annulée.", "warning")
        return redirect(url_for('raid.index'))

    device_path = f"/dev/{array_name}"
    try:
        # ÉTAPE 1: Arrêter la grappe si elle est active
        subprocess.run(['sudo', 'mdadm', '--stop', device_path], capture_output=True)
        flash(f"Tentative d'arrêt de la grappe RAID {array_name}.", "info")

        # ÉTAPE 2: Trouver TOUTES les partitions du système
        result = subprocess.run(['lsblk', '-J', '-o', 'NAME,TYPE'], capture_output=True, text=True, check=True)
        all_devices = json.loads(result.stdout).get('blockdevices', [])
        def flatten(devices):
            flat_list = []
            for dev in devices:
                if dev.get('type') == 'part': flat_list.append(dev['name'])
                if 'children' in dev: flat_list.extend(flatten(dev['children']))
            return flat_list
        all_partitions = flatten(all_devices)

        # ÉTAPE 3: Nettoyer le superblock de TOUTES les partitions
        # C'est une approche "force brute" mais infaillible pour nettoyer les membres d'une grappe cassée.
        cleaned_count = 0
        for part_name in all_partitions:
            part_path = f"/dev/{part_name}"
            subprocess.run(['sudo', 'mdadm', '--zero-superblock', part_path], check=True)
            subprocess.run(['sudo', 'dd', 'if=/dev/zero', 'bs=1M', 'count=100', f'of={part_path}'], check=True)
            flash(f"Ancien superblock RAID nettoyé sur {part_path}.", "info")
            cleaned_count += 1
        
        # ÉTAPE 1: Arrêter la grappe si elle est active
        subprocess.run(['sudo', 'mdadm', '--remove', device_path], capture_output=True)
        flash(f"Tentative d'arrêt de la grappe RAID {array_name}.", "info")
        
        if cleaned_count > 0:
            flash(f"{cleaned_count} partition(s) nettoyée(s).", "success")
        else:
            flash("Aucun superblock trouvé à nettoyer. L'opération est terminée.", "warning")
        
    except Exception as e:
        flash(f"Une erreur est survenue lors de la destruction : {e}", "danger")

    return redirect(url_for('raid.index'))