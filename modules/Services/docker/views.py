from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required
import docker
from docker.errors import ImageNotFound
from docker.types import Mount

display_name = "Docker"
icon = "box-seam-fill"
bp = Blueprint('docker', __name__, template_folder='templates')

@bp.route('/')
@login_required
def index():
    containers_data = []
    try:
        client = docker.from_env()
        all_containers = client.containers.list(all=True)
        
        for container in all_containers:
            image_tags = 'Image Manquante'
            try:
                if container.image and container.image.tags:
                    image_tags = container.image.tags[0]
            except ImageNotFound:
                pass

            containers_data.append({
                'id': container.id,
                'short_id': container.short_id,
                'name': container.name,
                'status': container.status,
                'ports': container.ports,
                'image_tags': image_tags
            })
            
    except Exception as e:
        flash(f"Erreur de connexion au daemon Docker : {e}", "danger")

    return render_template('docker.html', containers=containers_data)

@bp.route('/<container_id>/<action>', methods=['POST'])
@login_required
def container_action(container_id, action):
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        if action == 'start': container.start(); flash(f"Conteneur '{container.name}' démarré.", "success")
        elif action == 'stop': container.stop(); flash(f"Conteneur '{container.name}' arrêté.", "success")
        elif action == 'restart': container.restart(); flash(f"Conteneur '{container.name}' redémarré.", "success")
        elif action == 'remove':
            if container.status == 'running': container.stop()
            container.remove(v=True); flash(f"Conteneur '{container.name}' supprimé.", "success")
    except Exception as e:
        flash(f"Une erreur est survenue : {e}", "danger")
    return redirect(url_for('docker.index'))

@bp.route('/<container_id>/logs')
@login_required
def container_logs(container_id):
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        logs = container.logs(tail=200).decode('utf-8')
    except Exception as e:
        flash(f"Erreur lors de la lecture des logs : {e}", "danger")
        return redirect(url_for('docker.index'))
    return render_template('docker_logs.html', container_name=container.name, logs=logs)

@bp.route('/images')
@login_required
def images():
    images = []
    search_results = []
    search_term = request.args.get('search', '')
    try:
        client = docker.from_env()
        images = client.images.list()
        if search_term:
            search_results = client.images.search(term=search_term, limit=20)
    except Exception as e:
        flash(f"Erreur de communication avec Docker : {e}", "danger")
    return render_template('docker_images.html', images=images, search_results=search_results, search_term=search_term)

@bp.route('/images/pull', methods=['POST'])
@login_required
def pull_image():
    image_name = request.form.get('image_name')
    if not image_name:
        flash("Le nom de l'image est requis.", "warning")
        return redirect(url_for('docker.images'))
    try:
        client = docker.from_env()
        flash(f"Téléchargement de l'image '{image_name}' en cours...", "info")
        client.images.pull(image_name)
        flash(f"L'image '{image_name}' a été téléchargée.", "success")
    except Exception as e:
        flash(f"Erreur lors du téléchargement de l'image : {e}", "danger")
    return redirect(url_for('docker.images'))

@bp.route('/images/delete/<image_id>', methods=['POST'])
@login_required
def delete_image(image_id):
    try:
        client = docker.from_env()
        client.images.remove(image=image_id, force=True)
        flash(f"Image supprimée avec succès.", "success")
    except Exception as e:
        flash(f"Une erreur est survenue : {e}", "danger")
    return redirect(url_for('docker.images'))

@bp.route('/images/run/<path:image_name>')
@login_required
def run_image_form(image_name):
    return render_template('run_image.html', image_name=image_name)

@bp.route('/images/run/execute', methods=['POST'])
@login_required
def run_image_execute():
    image_name = request.form.get('image_name')
    container_name = request.form.get('container_name')
    restart_policy = request.form.get('restart_policy')
    
    ports = {}
    for p in request.form.get('ports', '').splitlines():
        if ':' in p:
            parts = p.split(':', 1)
            if len(parts) == 2 and parts[0].strip().isdigit():
                ports[parts[1].strip()] = int(parts[0].strip())

    volumes = []
    for v in request.form.get('volumes', '').splitlines():
        if ':' in v:
            parts = v.split(':', 1)
            if len(parts) == 2:
                volumes.append(Mount(target=parts[1].strip(), source=parts[0].strip(), type='bind'))

    environment = []
    for e in request.form.get('environment', '').splitlines():
        if '=' in e:
            environment.append(e.strip())

    try:
        client = docker.from_env()
        client.containers.run(
            image=image_name,
            name=container_name,
            detach=True,
            restart_policy={"name": restart_policy},
            ports=ports,
            mounts=volumes,
            environment=environment
        )
        flash(f"Le conteneur '{container_name}' a été lancé avec succès.", "success")
    except Exception as e:
        flash(f"Erreur lors du lancement du conteneur : {e}", "danger")
        return redirect(url_for('docker.run_image_form', image_name=image_name))
        
    return redirect(url_for('docker.index'))