import os
import importlib
from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO
from collections import defaultdict
import psutil

from models import db, User, StatsHistory

app = Flask(__name__)
app.config.from_pyfile('config.py')
db.init_app(app)

socketio = SocketIO(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

categorized_modules = defaultdict(list)

def register_modules():
    module_folder = os.path.join(os.path.dirname(__file__), 'modules')
    if not os.path.exists(module_folder): return
    
    categorized_modules.clear()
    
    for category_name in os.listdir(module_folder):
        category_path = os.path.join(module_folder, category_name)
        if os.path.isdir(category_path):
            for module_name in os.listdir(category_path):
                module_path = os.path.join(category_path, module_name)
                if os.path.isdir(module_path) and os.path.exists(os.path.join(module_path, 'views.py')):
                    try:
                        spec = importlib.util.spec_from_file_location(
                            f"modules.{category_name}.{module_name}.views",
                            os.path.join(module_path, 'views.py')
                        )
                        module_views = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module_views)

                        if hasattr(module_views, 'bp'):
                            app.register_blueprint(module_views.bp, url_prefix=f'/{module_name}')
                            display_name = getattr(module_views, 'display_name', module_name.capitalize())
                            icon = getattr(module_views, 'icon', 'box')
                            
                            categorized_modules[category_name].append({
                                'name': display_name, 
                                'endpoint': f"{module_name}.index", 
                                'icon': icon,
                                'id': module_name
                            })
                            print(f"Module '{module_name}' chargé dans la catégorie '{category_name}'.")

                    except Exception as e:
                        print(f"Erreur lors du chargement du module {module_name}: {e}")

register_modules()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_modules():
    sorted_categories = dict(sorted(categorized_modules.items()))
    return dict(categorized_modules=sorted_categories)

@app.route('/toggle-theme')
@login_required
def toggle_theme():
    current_theme = session.get('theme', 'light')
    session['theme'] = 'dark' if current_theme == 'light' else 'light'
    return redirect(request.referrer or url_for('index'))

@app.route('/')
@login_required
def index():
    cpu_percent = psutil.cpu_percent()
    ram_percent = psutil.virtual_memory().percent
    
    storage_info = None
    max_size = 0
    try:
        partitions = psutil.disk_partitions()
        for p in partitions:
            if p.mountpoint and p.mountpoint.startswith('/mnt/'):
                usage = psutil.disk_usage(p.mountpoint)
                if usage.total > max_size:
                    max_size = usage.total
                    storage_info = {
                        'mountpoint': p.mountpoint,
                        'total': usage.total / (1024**3),
                        'used': usage.used / (1024**3),
                        'percent': usage.percent
                    }
    except Exception:
        pass

    return render_template('index.html', 
                           user=current_user, 
                           cpu=cpu_percent, 
                           ram=ram_percent,
                           storage=storage_info)

@app.route('/login', methods=['GET', 'POST'])
def login():
    registration_allowed = User.query.first() is None
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
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
        flash("L'inscription est désactivée.", "warning")
        return redirect(url_for('login'))
    if request.method == 'POST':
        new_user = User(username=request.form['username'])
        new_user.set_password(request.form['password'])
        db.session.add(new_user)
        db.session.commit()
        flash('Compte administrateur créé.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)