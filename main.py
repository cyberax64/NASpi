import os
import importlib
from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# On importe nos modèles et l'objet db depuis le nouveau fichier
from models import db, User, StatsHistory

app = Flask(__name__)
app.config.from_pyfile('config.py')

# On initialise la base de données avec notre application
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."

loaded_modules = []

def register_modules():
    module_folder = os.path.join(os.path.dirname(__file__), 'modules')
    if not os.path.exists(module_folder): return
    
    loaded_modules.clear()
    
    for module_name in os.listdir(module_folder):
        module_path = os.path.join(module_folder, module_name)
        if os.path.isdir(module_path) and os.path.exists(os.path.join(module_path, 'views.py')):
            try:
                spec = importlib.util.spec_from_file_location(
                    f"modules.{module_name}.views",
                    os.path.join(module_path, 'views.py')
                )
                module_views = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module_views)

                if hasattr(module_views, 'bp'):
                    app.register_blueprint(module_views.bp, url_prefix=f'/{module_name}')
                    display_name = getattr(module_views, 'display_name', module_name.capitalize())
                    icon = getattr(module_views, 'icon', 'box')
                    loaded_modules.append({'name': display_name, 'endpoint': f"{module_name}.index", 'icon': icon})
                    print(f"Module '{module_name}' chargé avec succès.")

            except Exception as e:
                print(f"Erreur lors du chargement du module {module_name}: {e}")

register_modules()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_modules():
    return dict(modules=loaded_modules)

@app.route('/toggle-theme')
@login_required
def toggle_theme():
    current_theme = session.get('theme', 'light')
    if current_theme == 'dark':
        session['theme'] = 'light'
    else:
        session['theme'] = 'dark'
    return redirect(request.referrer or url_for('index'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    registration_allowed = User.query.first() is None
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            session['theme'] = 'light'
            return redirect(url_for('index'))
        else:
            flash('Identifiants invalides.', 'danger')
    return render_template('login.html', registration_allowed=registration_allowed)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if User.query.first() is not None:
        flash("L'inscription est désactivée car un compte administrateur existe déjà.", "warning")
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Compte administrateur créé avec succès ! Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

if __name__ == '__main__':
    # On ajoute ce bloc pour créer la BDD automatiquement
    with app.app_context():
        db.create_all()
    
    app.run(debug=True, host='0.0.0.0', port=5001)
