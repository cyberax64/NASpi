# config.py

import os

# Génère une clé secrète. Changez-la pour une chaîne de caractères complexe en production.
SECRET_KEY = os.urandom(24)

# Configuration de la base de données SQLite
# os.path.abspath(os.path.dirname(__file__)) pointe vers le dossier courant du projet
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
