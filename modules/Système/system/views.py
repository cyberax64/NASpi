from flask import Blueprint, render_template, flash, jsonify
from flask_login import login_required
import psutil
import platform
import socket
from datetime import datetime, timedelta
import subprocess
from models import StatsHistory

display_name = "Infos Système"
icon = "info-circle-fill"
bp = Blueprint('system', __name__, template_folder='templates')

def get_cpu_model():
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if "Model name" in line:
                    return line.split(':')[1].strip()
    except:
        return "Inconnu"

def format_bytes(byte_count):
    if byte_count is None: return "N/A"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while byte_count >= power and n < len(power_labels):
        byte_count /= power
        n += 1
    return f"{byte_count:.2f} {power_labels[n]}B"

@bp.route('/')
@login_required
def index():
    system_info = {
        'hostname': socket.gethostname(),
        'os': platform.system(),
        'os_release': platform.release(),
        'os_version': platform.version(),
    }
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    system_info['uptime_days'] = uptime.days
    system_info['uptime_hours'] = uptime.seconds // 3600
    system_info['uptime_minutes'] = (uptime.seconds // 60) % 60

    cpu_info = {
        'model': get_cpu_model(),
        'physical_cores': psutil.cpu_count(logical=False),
        'total_cores': psutil.cpu_count(logical=True),
        'freq_current': f"{psutil.cpu_freq().current:.0f} Mhz",
        'load_avg': f"{psutil.getloadavg()[0]:.2f}, {psutil.getloadavg()[1]:.2f}, {psutil.getloadavg()[2]:.2f}",
        'usage': psutil.cpu_percent()
    }

    mem_info = {
        'ram_total': format_bytes(psutil.virtual_memory().total),
        'ram_used': format_bytes(psutil.virtual_memory().used),
        'ram_percent': psutil.virtual_memory().percent,
        'swap_total': format_bytes(psutil.swap_memory().total),
        'swap_used': format_bytes(psutil.swap_memory().used),
        'swap_percent': psutil.swap_memory().percent
    }
    
    net_info = {'ip': 'N/A', 'netmask': 'N/A'}
    for interface, addrs in psutil.net_if_addrs().items():
        if interface != 'lo':
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    net_info['ip'] = addr.address
                    net_info['netmask'] = addr.netmask
                    break
            if net_info['ip'] != 'N/A': break
    
    net_io = psutil.net_io_counters()
    net_info['bytes_sent'] = format_bytes(net_io.bytes_sent)
    net_info['bytes_recv'] = format_bytes(net_io.bytes_recv)

    mounted_drives = []
    try:
        partitions = psutil.disk_partitions()
        for p in partitions:
            if p.fstype and p.device.startswith('/dev/'):
                usage = psutil.disk_usage(p.mountpoint)
                mounted_drives.append({
                    'device': p.device, 'mountpoint': p.mountpoint, 'fstype': p.fstype,
                    'usage': usage, 'total': format_bytes(usage.total), 'used': format_bytes(usage.used)
                })
    except Exception as e:
        flash(f"Erreur lors de la lecture des partitions montées : {e}", "danger")

    system_logs = "Impossible de lire les journaux système."
    try:
        result = subprocess.run(['journalctl', '-n', '25', '--no-pager', '-r'], capture_output=True, text=True, check=True)
        system_logs = result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return render_template('system.html', 
                           system=system_info, cpu=cpu_info, memory=mem_info,
                           network=net_info, drives=mounted_drives, logs=system_logs)

@bp.route('/stats-data')
@login_required
def stats_data():
    time_threshold = datetime.utcnow() - timedelta(hours=24)
    stats = StatsHistory.query.filter(StatsHistory.timestamp >= time_threshold).order_by(StatsHistory.timestamp.asc()).all()
    
    labels = [s.timestamp.strftime('%H:%M') for s in stats]
    cpu_data = [s.cpu_percent for s in stats]
    ram_data = [s.ram_percent for s in stats]
    
    return jsonify({'labels': labels, 'cpu': cpu_data, 'ram': ram_data})