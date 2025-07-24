# NAS Panel pour Raspberry Pi 5 🚀

![Licence MIT](https://img.shields.io/github/license/cyberax64/NASpi?style=for-the-badge)

Une interface web complète, développée en Python avec Flask, pour transformer votre Raspberry Pi 5 en un puissant NAS et serveur domestique. Gérez votre stockage, vos services et votre système, le tout depuis une interface simple et moderne.

![Screenshot du NAS Panel](https://raw.githubusercontent.com/cyberax64/NASpi/main/capture.png)

---

## ✨ Fonctionnalités

Ce panneau de contrôle est organisé par catégories pour une gestion intuitive :

### 📊 Système
* **Tableau de Bord :** Vue d'ensemble avec widgets pour l'utilisation CPU, RAM et du stockage principal.
* **Infos Système :** Dashboard détaillé avec graphiques de performance, état du réseau, journaux système et liste des disques montés.
* **Terminal :** Accès direct à un terminal `root` sécurisé dans le navigateur.

### 💾 Stockage
* **Gestion des Disques :** Visualisation des disques, partitions et grappes RAID. Outils complets pour partitionner (multiples partitions, choix du FS), formater, monter/démonter, ajouter/supprimer des partitions, et effacer des disques.
* **Gestion RAID :** Création et destruction de grappes RAID logiciel (0, 1, 5, 6). Visualisation de l'état des grappes (actives, en synchronisation, cassées).
* **Mise à jour :** Gestion des mise à jour de debian (apt).
* **Mise à jour panel:** Gestion des mise à jour du panel.

### 🌐 Services
* **Partages Samba :** Gestion des partages réseau, des utilisateurs Samba et des permissions de lecture/écriture par utilisateur.
* **Conteneurs Docker :** Gestion complète du cycle de vie des conteneurs (démarrer, arrêter, etc.), consultation des logs, recherche et téléchargement d'images, et lancement de nouveaux conteneurs avec une configuration détaillée (ports, volumes, variables).
* **VPN WireGuard :** Gestion du VPN WireGuard.

### 🔐 Administration
* **Pare-feu (UFW) :** Activation/désactivation et gestion simplifiée des règles du pare-feu.
* **Géolocalisation :** Module de suivi GPS avec carte interactive (hors-ligne possible).
* **Réseau :** État des interfaces réseau, configuration d'IP statique et gestion du Wi-Fi (mode Client / Point d'Accès).

### 🎨 Interface
* **Sécurisée :** Connexion obligatoire et inscription unique pour le compte administrateur.
* **Personnalisable :** Choix entre un thème clair et un thème sombre.

---

## 🛠️ Prérequis

#### Matériel
* Un Raspberry Pi 5 (4Go de RAM ou plus recommandé).
* Une alimentation USB-C officielle (5V/5A).
* Une carte microSD pour le système.
* Un ou plusieurs disques durs externes ou SSD.

#### Logiciel
* **Raspberry Pi OS (Bookworm) 64-bit** ou un système Debian équivalent (Proxmox Host inclus).
* Accès au terminal en tant que `root` ou avec `sudo`.

---

## 🚀 Installation

L'installation est entièrement automatisée.

1.  Clonez le dépôt :
    ```bash
    git clone https://github.com/cyberax64/NASpi.git
    ```
2.  Naviguez dans le dossier :
    ```bash
    cd NASpi
    ```
3.  Rendez le script exécutable :
    ```bash
    chmod +x install.sh
    ```
4.  Lancez l'installation en tant que `root` ou avec `sudo` :
    ```bash
    sudo ./install.sh
    ```
Le script installe toutes les dépendances, configure l'application dans `/opt/nas-panel` et la lance comme un service qui démarre automatiquement.

---

## 🚦 Premiers Pas

1.  Accédez à l'interface web depuis un autre appareil sur le même réseau :
    **`http://<adresse-ip-de-votre-pi>:5001`**

2.  La première page est celle de l'inscription. **Créez votre compte administrateur.** Après cette étape, l'inscription sera définitivement bloquée.

3.  **Permissions Docker (Important) :** Pour que le module Docker fonctionne, ajoutez votre utilisateur principal (par ex. `pi`) au groupe `docker` et redémarrez.
    ```bash
    sudo usermod -aG docker pi
    sudo reboot
    ```

Votre NAS Panel est prêt à être utilisé !
