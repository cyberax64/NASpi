# Fichier : modules/Administration/updater/views.py

from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required
import subprocess
import os

display_name = "Mise à Jour du Panel"
icon = "cloud-download-fill"
bp = Blueprint('updater', __name__, template_folder='templates')

APP_DIR = '/opt/nas-panel'

def get_git_status():
    """Vérifie l'état du dépôt Git local par rapport à l'origine."""
    status = {'update_available': False, 'local_commit': 'N/A', 'remote_commit': 'N/A'}
    try:
        # Met à jour la connaissance du dépôt distant sans rien changer localement
        subprocess.run(['sudo', 'git', '-C', APP_DIR, 'fetch'], check=True)
        
        # Récupère le hash du commit local (HEAD)
        local_hash = subprocess.run(
            ['sudo', 'git', '-C', APP_DIR, 'rev-parse', 'HEAD'], 
            capture_output=True, text=True, check=True
        ).stdout.strip()
        status['local_commit'] = local_hash[:7] # On garde une version courte

        # Récupère le hash du commit distant (sur la branche main)
        remote_hash = subprocess.run(
            ['sudo', 'git', '-C', APP_DIR, 'rev-parse', 'origin/main'], 
            capture_output=True, text=True, check=True
        ).stdout.strip()
        status['remote_commit'] = remote_hash[:7]

        # Compare les deux
        if local_hash != remote_hash:
            status['update_available'] = True

    except Exception as e:
        flash(f"Erreur lors de la vérification Git : {e}", "danger")
        status['update_available'] = False
        
    return status

@bp.route('/')
@login_required
def index():
    git_status = get_git_status()
    return render_template('updater.html', status=git_status)

@bp.route('/run', methods=['POST'])
@login_required
def run_update():
    try:
        flash("Lancement de la mise à jour...", "info")
        
        # Exécute git pull pour télécharger les mises à jour
        pull_result = subprocess.run(
            ['sudo', 'git', '-C', APP_DIR, 'pull', 'origin', 'main'],
            check=True, capture_output=True, text=True
        )
        flash(f"Mise à jour téléchargée avec succès. \n{pull_result.stdout}", "success")
        
        # Redémarre le service pour appliquer les changements
        flash("Redémarrage de l'application pour appliquer les mises à jour...", "warning")
        subprocess.run(['sudo', 'systemctl', 'restart', 'nas-panel.service'], check=True)
        
        # Ce redirect ne sera probablement jamais atteint car le serveur redémarre,
        # mais il est bon de l'avoir.
        return redirect(url_for('updater.index'))
        
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors de la mise à jour : {e.stderr}", "danger")
        
    return redirect(url_for('updater.index'))