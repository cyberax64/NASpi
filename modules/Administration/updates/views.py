# Fichier : modules/updates/views.py

from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required
from main import socketio
import subprocess
import re

display_name = "Mises à Jour (apt)"
icon = "cloud-arrow-up-fill"
bp = Blueprint('updates', __name__, template_folder='templates')

def parse_upgradable_packages(output):
    """Analyse la sortie de 'apt list --upgradable'."""
    packages = []
    lines = output.strip().splitlines()
    if len(lines) <= 1:
        return []
    
    for line in lines[1:]: # Ignorer la première ligne "Listing..."
        parts = line.split()
        if len(parts) >= 4:
            packages.append({
                'name': parts[0].split('/')[0],
                'new_version': parts[1],
                'architecture': parts[2],
                'current_version': parts[4]
            })
    return packages

@bp.route('/')
@login_required
def index():
    packages = []
    try:
        # 1. Mettre à jour la liste des paquets
        flash("Recherche des mises à jour en cours...", "info")
        subprocess.run(['sudo', 'apt-get', 'update'], capture_output=True, text=True, check=True)
        
        # 2. Lister les paquets qui peuvent être mis à jour
        result = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True, text=True, check=True)
        packages = parse_upgradable_packages(result.stdout)
        
        if not packages:
            flash("Votre système est à jour.", "success")
            
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors de la recherche des mises à jour : {e.stderr}", "danger")
    except Exception as e:
        flash(f"Une erreur inattendue est survenue : {e}", "danger")

    return render_template('updates.html', packages=packages)


@socketio.on('run_upgrade', namespace='/updates')
def run_upgrade():
    """Lance la mise à jour et envoie la sortie en temps réel."""
    try:
        # Commande de mise à jour non-interactive
        command = ['sudo', 'apt-get', 'upgrade', '-y']
        
        # On utilise Popen pour streamer la sortie
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # On lit la sortie ligne par ligne et on l'envoie au client
        for line in iter(process.stdout.readline, ''):
            socketio.emit('upgrade_log', {'log': line}, namespace='/updates')
        
        process.stdout.close()
        return_code = process.wait()
        
        if return_code == 0:
            socketio.emit('upgrade_log', {'log': '\n\n--- MISE À JOUR TERMINÉE AVEC SUCCÈS ---'}, namespace='/updates')
        else:
            socketio.emit('upgrade_log', {'log': f'\n\n--- ERREUR : Le processus s\'est terminé avec le code {return_code} ---'}, namespace='/updates')
            
    except Exception as e:
        socketio.emit('upgrade_log', {'log': f'\n\n--- ERREUR CRITIQUE DANS LE SCRIPT : {e} ---'}, namespace='/updates')
