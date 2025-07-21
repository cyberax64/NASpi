import psutil
from main import app
from models import db, StatsHistory

def collect_stats():
    """Collecte les stats actuelles et les insère dans la base de données."""
    with app.app_context():
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        net = psutil.net_io_counters()
        
        new_stat = StatsHistory(
            cpu_percent=cpu,
            ram_percent=ram,
            net_sent=net.bytes_sent,
            net_recv=net.bytes_recv
        )
        
        db.session.add(new_stat)
        db.session.commit()
        print(f"Statistiques collectées : CPU {cpu}%, RAM {ram}%")

if __name__ == '__main__':
    collect_stats()