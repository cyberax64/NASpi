# Fichier : modules/ufw/views.py

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
import subprocess
import re

display_name = "Pare-feu (UFW)"
icon = "shield-shaded"
bp = Blueprint('ufw', __name__, template_folder='templates')

def get_ufw_status():
    """Analyse la sortie de 'ufw status numbered' pour l'état et les règles."""
    status = "inconnu"
    rules = []
    try:
        # On utilise 'ufw status numbered' qui est facile à parser
        result = subprocess.run(['sudo', 'ufw', 'status', 'numbered'], capture_output=True, text=True)
        
        # Le code de retour est 0 même si le pare-feu est inactif
        output = result.stdout
        
        status_match = re.search(r'Status: (\w+)', output)
        if status_match:
            status = status_match.group(1)

        # Si le pare-feu est actif, on cherche les règles
        if status == 'active':
            # La regex cherche les lignes qui commencent par [ X]
            rule_lines = re.findall(r'(\[\s*\d+\].*)', output)
            for line in rule_lines:
                # On nettoie la ligne
                cleaned_line = re.sub(r'\s+', ' ', line).strip()
                parts = cleaned_line.split()
                # Ex: [ 1] 22/tcp ALLOW IN Anywhere
                rules.append({
                    'num': parts[0].replace('[','').replace(']',''),
                    'to': parts[1],
                    'action': parts[2],
                    'from': parts[4]
                })

    except Exception as e:
        flash(f"Erreur lors de la lecture du statut UFW : {e}", "danger")
    
    return status, rules

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST': # Gère l'ajout de règles
        action = request.form.get('action')
        rule = request.form.get('rule')
        try:
            command = ['sudo', 'ufw', action.lower(), rule]
            subprocess.run(command, check=True, capture_output=True, text=True)
            flash(f"Règle '{action} {rule}' ajoutée avec succès.", "success")
        except subprocess.CalledProcessError as e:
            flash(f"Erreur lors de l'ajout de la règle : {e.stderr}", "danger")
        return redirect(url_for('ufw.index'))

    status, rules = get_ufw_status()
    return render_template('ufw.html', status=status, rules=rules)

@bp.route('/toggle/<new_status>', methods=['POST'])
@login_required
def toggle_ufw(new_status):
    if new_status not in ['enable', 'disable']:
        flash("Action non valide.", "danger")
        return redirect(url_for('ufw.index'))
    
    try:
        command = ['sudo', 'ufw', '--force', new_status]
        subprocess.run(command, check=True)
        flash(f"Le pare-feu a été {'activé' if new_status == 'enable' else 'désactivé'}.", "success")
    except Exception as e:
        flash(f"Erreur lors du changement de statut du pare-feu : {e}", "danger")

    return redirect(url_for('ufw.index'))

@bp.route('/delete_rule/<rule_num>', methods=['POST'])
@login_required
def delete_rule(rule_num):
    try:
        # On utilise --force pour éviter la demande de confirmation y/n
        command = ['sudo', 'ufw', '--force', 'delete', rule_num]
        subprocess.run(command, check=True, capture_output=True, text=True)
        flash(f"Règle #{rule_num} supprimée avec succès.", "success")
    except subprocess.CalledProcessError as e:
        flash(f"Erreur lors de la suppression de la règle : {e.stderr}", "danger")

    return redirect(url_for('ufw.index'))
