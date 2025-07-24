from flask import Blueprint, render_template, flash, abort, redirect, url_for, request, send_from_directory
from flask_login import login_required
import os
import shutil
from datetime import datetime
from werkzeug.utils import secure_filename

display_name = "Explorateur"
icon = "folder-fill"
bp = Blueprint('explorer', __name__, template_folder='templates')

BASE_DIR = '/mnt'

def validate_path(path):
    """Sécurise un chemin pour s'assurer qu'il reste dans BASE_DIR."""
    full_path = os.path.join(BASE_DIR, path)
    real_path = os.path.realpath(full_path)
    if not real_path.startswith(os.path.realpath(BASE_DIR)):
        abort(403)
    return real_path

def get_dir_contents(path):
    items = []
    for item in os.listdir(path):
        try:
            item_path = os.path.join(path, item)
            stats = os.stat(item_path)
            items.append({
                'name': item,
                'is_dir': os.path.isdir(item_path),
                'size': stats.st_size,
                'modified': datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
        except FileNotFoundError:
            continue
    return sorted(items, key=lambda x: (not x['is_dir'], x['name'].lower()))

@bp.route('/')
@bp.route('/<path:subpath>')
@login_required
def index(subpath=''):
    real_path = validate_path(subpath)
    if not os.path.isdir(real_path):
        flash("Le dossier demandé n'existe pas.", "danger")
        return redirect(url_for('explorer.index'))

    contents = get_dir_contents(real_path)
    parent_path = None
    if real_path != os.path.realpath(BASE_DIR):
        parent_path = os.path.dirname(subpath) if subpath else ''

    return render_template('explorer.html', 
                           contents=contents, 
                           current_path=subpath, 
                           parent_path=parent_path)

@bp.route('/download/<path:filepath>')
@login_required
def download(filepath):
    real_path = validate_path(filepath)
    if os.path.isdir(real_path): abort(403)
    directory = os.path.dirname(real_path)
    filename = os.path.basename(real_path)
    return send_from_directory(directory, filename, as_attachment=True)

@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    path = request.form.get('path', '')
    if not path: # Sécurité
        flash("Le téléversement de fichiers est interdit à la racine de /mnt.", "danger")
        return redirect(url_for('explorer.index'))
        
    real_path = validate_path(path)
    files = request.files.getlist('files')
    for file in files:
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(real_path, filename))
            flash(f"Fichier '{filename}' téléversé.", "success")
    return redirect(url_for('explorer.index', subpath=path))

@bp.route('/mkdir', methods=['POST'])
@login_required
def mkdir():
    path = request.form.get('path', '')
    folder_name = request.form.get('folder_name')
    if not path: # Sécurité
        flash("La création de dossier est interdite à la racine de /mnt.", "danger")
        return redirect(url_for('explorer.index'))

    real_path = validate_path(path)
    if folder_name:
        new_dir_path = os.path.join(real_path, secure_filename(folder_name))
        os.makedirs(new_dir_path, exist_ok=True)
        flash(f"Dossier '{folder_name}' créé.", "success")
    return redirect(url_for('explorer.index', subpath=path))

@bp.route('/delete', methods=['POST'])
@login_required
def delete():
    path = request.form.get('path', '')
    item_name = request.form.get('item_name')
    if not path: # Sécurité
        flash("La suppression est interdite à la racine de /mnt.", "danger")
        return redirect(url_for('explorer.index'))
        
    real_item_path = validate_path(os.path.join(path, item_name))
    try:
        if os.path.isdir(real_item_path):
            shutil.rmtree(real_item_path)
        else:
            os.remove(real_item_path)
        flash(f"'{item_name}' supprimé avec succès.", "success")
    except Exception as e:
        flash(f"Erreur lors de la suppression : {e}", "danger")
    return redirect(url_for('explorer.index', subpath=path))

@bp.route('/rename', methods=['POST'])
@login_required
def rename():
    path = request.form.get('path', '')
    old_name = request.form.get('old_name')
    new_name = request.form.get('new_name')
    if not path: # Sécurité
        flash("Le renommage est interdit à la racine de /mnt.", "danger")
        return redirect(url_for('explorer.index'))

    if old_name and new_name:
        real_old_path = validate_path(os.path.join(path, old_name))
        real_new_path = validate_path(os.path.join(path, new_name))
        os.rename(real_old_path, real_new_path)
        flash(f"'{old_name}' renommé en '{new_name}'.", "success")
    return redirect(url_for('explorer.index', subpath=path))