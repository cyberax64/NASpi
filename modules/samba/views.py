from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
import configparser
import subprocess
import re

display_name = "Partages Samba"
icon = "hdd-network"
bp = Blueprint('samba', __name__, template_folder='templates')

SAMBA_CONF_PATH = '/etc/samba/smb.conf'

def read_samba_config():
    config = configparser.ConfigParser(comment_prefixes=('#', ';'), delimiters='=', interpolation=None)
    config.read(SAMBA_CONF_PATH)
    shares = []
    for section in config.sections():
        if section not in ['global', 'printers', 'print$']:
            share_info = dict(config.items(section))
            share_info['name'] = section
            shares.append(share_info)
    return shares

def write_samba_config(config):
    with open(SAMBA_CONF_PATH, 'w') as configfile:
        config.write(configfile)

def restart_samba():
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'smbd.service'], check=True)
        return True
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors du redémarrage de Samba : {e}", "danger")
        return False

def get_samba_users():
    users = []
    try:
        result = subprocess.run(['sudo', 'pdbedit', '-L'], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            users.append(line.split(':')[0])
    except (subprocess.CalledProcessError, FileNotFoundError):
        flash("La commande 'pdbedit' n'a pas pu être exécutée.", "danger")
    return users

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        share_name = request.form['share_name']
        share_path = request.form['share_path']
        guest_ok = request.form['guest_ok']
        read_list = ','.join(request.form.getlist('read_users'))
        write_list = ','.join(request.form.getlist('write_users'))

        config = configparser.ConfigParser(comment_prefixes=('#', ';'), delimiters='=', interpolation=None)
        config.read(SAMBA_CONF_PATH)

        if not config.has_section(share_name):
            config.add_section(share_name)
            config.set(share_name, 'path', share_path)
            config.set(share_name, 'guest ok', guest_ok)
            config.set(share_name, 'browsable', 'yes')
            config.set(share_name, 'read only', 'yes')
            if write_list: config.set(share_name, 'write list', write_list)
            if read_list: config.set(share_name, 'read list', read_list)
            
            write_samba_config(config)
            if restart_samba():
                flash(f"Le partage '{share_name}' a été ajouté.", "success")
        else:
            flash(f"Le partage '{share_name}' existe déjà !", "warning")
        
        return redirect(url_for('samba.index'))

    shares = read_samba_config()
    samba_users = get_samba_users()
    return render_template('samba.html', shares=shares, all_users=samba_users)

@bp.route('/edit/<share_name>')
@login_required
def edit_share(share_name):
    config = configparser.ConfigParser(comment_prefixes=('#', ';'), delimiters='=', interpolation=None)
    config.read(SAMBA_CONF_PATH)
    if not config.has_section(share_name):
        flash(f"Le partage '{share_name}' n'existe pas.", "danger")
        return redirect(url_for('samba.index'))
    
    share_details = dict(config.items(share_name))
    share_details['name'] = share_name
    share_details['read_list'] = [user.strip() for user in share_details.get('read list', '').split(',') if user]
    share_details['write_list'] = [user.strip() for user in share_details.get('write list', '').split(',') if user]
    
    all_samba_users = get_samba_users()
    
    return render_template('edit_share.html', share=share_details, all_users=all_samba_users)

@bp.route('/edit/<share_name>/save', methods=['POST'])
@login_required
def save_share(share_name):
    config = configparser.ConfigParser(comment_prefixes=('#', ';'), delimiters='=', interpolation=None)
    config.read(SAMBA_CONF_PATH)
    if not config.has_section(share_name):
        flash(f"Le partage '{share_name}' n'existe pas.", "danger")
        return redirect(url_for('samba.index'))

    config.set(share_name, 'path', request.form['share_path'])
    config.set(share_name, 'guest ok', request.form['guest_ok'])
    
    read_list = ','.join(request.form.getlist('read_users'))
    write_list = ','.join(request.form.getlist('write_users'))
    
    config.set(share_name, 'read only', 'yes')

    if write_list: config.set(share_name, 'write list', write_list)
    elif config.has_option(share_name, 'write list'): config.remove_option(share_name, 'write list')
        
    if read_list: config.set(share_name, 'read list', read_list)
    elif config.has_option(share_name, 'read list'): config.remove_option(share_name, 'read list')

    write_samba_config(config)
    if restart_samba():
        flash(f"Le partage '{share_name}' a été mis à jour.", "success")

    return redirect(url_for('samba.index'))

@bp.route('/delete/<share_name>', methods=['POST'])
@login_required
def delete_share(share_name):
    config = configparser.ConfigParser(comment_prefixes=('#', ';'), delimiters='=', interpolation=None)
    config.read(SAMBA_CONF_PATH)
    if config.has_section(share_name):
        config.remove_section(share_name)
        write_samba_config(config)
        if restart_samba():
            flash(f"Le partage '{share_name}' a été supprimé.", "success")
    else:
        flash("Le partage n'a pas été trouvé.", "warning")
    return redirect(url_for('samba.index'))

@bp.route('/users')
@login_required
def users():
    samba_users = get_samba_users()
    return render_template('samba_users.html', samba_users=samba_users)

@bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        flash("Nom d'utilisateur et mot de passe requis.", "danger")
        return redirect(url_for('samba.users'))
    try:
        subprocess.run(['id', '-u', username], check=True, capture_output=True)
        flash(f"L'utilisateur système '{username}' existe déjà.", "danger")
        return redirect(url_for('samba.users'))
    except subprocess.CalledProcessError:
        pass
    try:
        subprocess.run(['sudo', 'useradd', '-M', '-s', '/usr/sbin/nologin', username], check=True)
        smbpasswd_input = f"{password}\n{password}\n"
        subprocess.run(['sudo', 'smbpasswd', '-a', username], input=smbpasswd_input, text=True, check=True)
        flash(f"Utilisateur Samba '{username}' ajouté.", "success")
    except subprocess.CalledProcessError as e:
        subprocess.run(['sudo', 'userdel', username], capture_output=True)
        flash(f"Erreur lors de l'ajout de l'utilisateur : {e.stderr or e}", "danger")
    return redirect(url_for('samba.users'))

@bp.route('/users/delete/<username>', methods=['POST'])
@login_required
def delete_user(username):
    if username in ['root', 'pi', 'www-data']:
        flash(f"La suppression de l'utilisateur '{username}' est interdite.", "danger")
        return redirect(url_for('samba.users'))
    try:
        subprocess.run(['sudo', 'smbpasswd', '-x', username], check=True)
        subprocess.run(['sudo', 'userdel', username], check=True)
        flash(f"Utilisateur '{username}' supprimé avec succès.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors de la suppression de l'utilisateur : {e.stderr or e}", "danger")
    return redirect(url_for('samba.users'))