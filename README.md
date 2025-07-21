NAS Panel pour Raspberry Pi 5 🚀

Une interface web complète, développée en Python avec Flask, pour transformer votre Raspberry Pi 5 en un puissant NAS et serveur domestique. Gérez vos disques, partages, conteneurs Docker et bien plus, le tout depuis une interface simple et moderne.

![Screenshot du NAS Panel](https://raw.githubusercontent.com/cyberax64/NASpi/main/capture.png)

✨ Fonctionnalités

Ce panneau de contrôle a été conçu pour être à la fois puissant et intuitif. Il inclut les modules suivants :

    📊 Tableau de Bord Système :

        Statistiques en temps réel (CPU, RAM, Swap, Réseau).

        Graphiques de performance sur les dernières 24 heures.

        Informations système (OS, noyau, uptime).

        Liste des systèmes de fichiers montés et leur utilisation.

        Vue des derniers journaux système.

    💾 Gestion des Disques :

        Visualisation des disques physiques, partitions et grappes RAID.

        Partitionnement de disques bruts avec choix du système de fichiers (ext4, btrfs, swap, raid).

        Formatage, montage/démontage de partitions.

        Ajout de partitions dans l'espace non alloué.

        Suppression de partitions individuelles.

        Effacement complet et sécurisé d'un disque (wipefs).

    ⚙️ Gestion RAID :

        Création de grappes RAID logiciel (mdadm) de niveau 0, 1, 5, 6.

        Visualisation de l'état des grappes (actives, en synchronisation, cassées).

        Destruction propre des grappes RAID.

        Détection intelligente des partitions éligibles pour le RAID.

    📁 Partages Samba :

        Création et gestion des dossiers partagés.

        Gestion des utilisateurs Samba (création/suppression).

        Gestion fine des permissions par utilisateur (lecture seule, lecture/écriture) via une interface à cases à cocher.

    🐳 Gestion Docker :

        Liste de tous les conteneurs (actifs et arrêtés).

        Actions de base : Démarrer, arrêter, redémarrer, supprimer.

        Visualisation des logs des conteneurs.

        Gestion des images : chercher sur le Docker Hub, télécharger (pull), lister et supprimer les images locales.

        Lancement de nouveaux conteneurs avec configuration détaillée (nom, ports, volumes, variables d'environnement).

    🌐 Gestion du Réseau :

        Visualisation de l'état des interfaces (Ethernet, Wi-Fi, etc.).

        Configuration d'adresse IP statique (compatible systemd-networkd).

        Gestion du Wi-Fi : scan des réseaux, connexion en mode Client, et basculement en mode Point d'Accès (Hotspot).

    🎨 Interface :

        Interface sécurisée avec page de connexion.

        Inscription unique pour le premier utilisateur (administrateur).

        Choix entre un thème clair et un thème sombre, mémorisé par session.

🛠️ Prérequis

Matériel

    Un Raspberry Pi 5 (4Go de RAM ou plus recommandé).

    Une alimentation USB-C officielle (5V/5A).

    Une carte microSD pour le système.

    Un ou plusieurs disques durs externes ou SSD pour le stockage.

Logiciel

    Raspberry Pi OS (Bookworm) 64-bit, fraîchement installé.

    Une connexion SSH ou un accès direct au terminal.

🚀 Installation

L'installation est entièrement automatisée grâce à un script.

Clonez ce dépôt sur votre Raspberry Pi en root:
```bash
git clone https://github.com/cyberax64/NASpi
```

Naviguez dans le dossier du projet :
```bash
cd NASpi
```
Rendez le script d'installation exécutable :
```bash
chmod +x install.sh
```

Lancez le script avec les droits sudo :
```bash
./install.sh
```

Le script va s'occuper de tout : installer les paquets système, copier les fichiers dans /opt/nas-panel, installer les dépendances Python, et configurer l'application pour qu'elle se lance automatiquement au démarrage.

🚦 Premiers Pas

    Une fois l'installation terminée, accédez à l'interface web depuis un autre ordinateur sur le même réseau :
    http://<adresse-ip-de-votre-pi>:5001

    La première page que vous verrez est celle de l'inscription. Créez votre compte administrateur. Attention : une fois ce premier compte créé, la page d'inscription sera définitivement désactivée.

    Permission Docker (Important) : Pour que le module Docker fonctionne, connectez-vous en SSH et ajoutez votre utilisateur principal (par exemple pi) au groupe docker :
    Bash

    sudo usermod -aG docker pi

    Déconnectez-vous puis reconnectez-vous à votre session SSH pour que ce changement soit pris en compte.

Votre NAS Panel est prêt !
