# Fichier : modules/terminal/views.py

from flask import Blueprint, render_template, request # 'request' a été ajouté ici
from flask_login import login_required
from main import socketio
import os
import pty
import select

display_name = "Terminal"
icon = "terminal-fill"
bp = Blueprint('terminal', __name__, template_folder='templates')

user_terminals = {}

@bp.route('/')
@login_required
def index():
    return render_template('terminal.html')

@socketio.on('connect', namespace='/terminal')
def connect():
    if request.sid in user_terminals:
        return

    (child_pid, fd) = pty.fork()
    
    if child_pid == 0:
        os.execv('/bin/bash', ['/bin/bash'])
    else:
        user_terminals[request.sid] = {'pid': child_pid, 'fd': fd}
        socketio.start_background_task(target=read_and_forward_pty_output, sid=request.sid)
        print(f"Terminal ouvert pour le client {request.sid}")

@socketio.on('disconnect', namespace='/terminal')
def disconnect():
    if request.sid in user_terminals:
        terminal_info = user_terminals.pop(request.sid)
        os.close(terminal_info['fd'])
        try:
            os.kill(terminal_info['pid'], 9)
        except OSError:
            pass
        print(f"Terminal fermé pour le client {request.sid}")

@socketio.on('terminal_input', namespace='/terminal')
def terminal_input(data):
    if request.sid in user_terminals:
        fd = user_terminals[request.sid]['fd']
        os.write(fd, data.encode())

def read_and_forward_pty_output(sid):
    while sid in user_terminals:
        fd = user_terminals[sid]['fd']
        try:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                output = os.read(fd, 1024)
                if output:
                    socketio.emit('terminal_output', output.decode(errors='ignore'), namespace='/terminal', to=sid)
                else: # Si la sortie est vide, le processus a terminé
                    break
        except OSError:
            break
        socketio.sleep(0.01)
    
    # Nettoyage final si la tâche se termine
    if sid in user_terminals:
        user_terminals.pop(sid)
        print(f"Tâche de lecture terminée et terminal nettoyé pour le client {sid}")