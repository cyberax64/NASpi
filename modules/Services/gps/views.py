# Fichier : modules/gps/views.py

from flask import Blueprint, render_template, flash, jsonify
from flask_login import login_required
from gps import gps, WATCH_ENABLE, WATCH_NEWSTYLE

display_name = "Géolocalisation"
icon = "geo-alt-fill"
bp = Blueprint('gps', __name__, template_folder='templates')

# On initialise la session GPS une seule fois
try:
    gpsd_session = gps(mode=WATCH_ENABLE|WATCH_NEWSTYLE)
except Exception as e:
    # Si gpsd n'est pas lancé, on crée un objet vide pour éviter de planter
    gpsd_session = None
    print(f"AVERTISSEMENT : Impossible de se connecter à gpsd. {e}")

@bp.route('/')
@login_required
def index():
    if not gpsd_session:
        flash("Le service gpsd n'est pas accessible. Assurez-vous qu'il est installé et démarré.", "danger")
    return render_template('gps.html')

@bp.route('/data')
@login_required
def gps_data():
    """Cette route API fournit les données GPS au format JSON."""
    if not gpsd_session:
        return jsonify({'error': 'gpsd non disponible'}), 500

    if gpsd_session.read() == 0:
        if gpsd_session.valid & gps.LATLON_SET:
            return jsonify({
                'latitude': gpsd_session.fix.latitude,
                'longitude': gpsd_session.fix.longitude,
                'altitude': gpsd_session.fix.altitude if gpsd_session.valid & gps.ALTITUDE_SET else 'N/A',
                'speed': gpsd_session.fix.speed if gpsd_session.valid & gps.SPEED_SET else 'N/A',
                'time': gpsd_session.fix.time if gpsd_session.valid & gps.TIME_SET else 'N/A',
                'satellites': len(gpsd_session.satellites)
            })
    
    # Si on n'a pas encore de "fix"
    return jsonify({'error': 'En attente de données satellites...'})
