# -Projet-Natacha-Cluster-IA-Distribu-Multi-Backend

![Schéma de l'Architecture Natacha](architecture-natacha.png)

Natacha est un assistant personnel modulaire conçu pour fonctionner sur un cluster de machines hétérogènes. Contrairement aux solutions monolithiques, Natacha fragmente l'intelligence (Cerveau, Oreille, Bouche) pour exploiter le meilleur de chaque architecture matérielle (Intel Core, AMD Ryzen, Rockchip SIC).




​🏗️ Architecture du Système

​Le projet repose sur une communication hybride :

​MQTT : Pour la logique de contrôle et les échanges de texte.

​UDP / GStreamer : Pour le transport audio basse latence entre les nœuds.

​Les Trois Piliers

​L'Oreille (Transcription) : Capture audio et conversion STT (Speech-To-Text).

​Le Cerveau (Inférence) : LLM local pour le raisonnement et la gestion des commandes.

​La Bouche (Synthèse) : TTS (Text-To-Speech) et sortie audio physique.


​🚀 Compatibilité Matérielle (Multi-Backend)



# 🛠️ Installation & Déploiement

📋 Prérequis Système

Le projet Natacha est développé et optimisé pour Ubuntu 24.04 LTS. L'utilisation de cette version garantit
la stabilité des flux audio et la gestion correcte des environnements Conda.

. Système d'exploitation :

    OS : Ubuntu 24.04 LTS (recommandé sur Ryzen et Intel).

    Architecture : x86_64 ou ARM64 (Orange Pi).
    

## 0. Prérequis : Installation de Miniconda3

Si Miniconda n'est pas encore présent sur votre système, vous devez l'installer en premier. La version dépend du type de processeur de votre nœud.

Pour un PC classique (Intel/AMD - ex: i5, Ryzen) :
```
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
./Miniconda3-latest-Linux-x86_64.sh
```

## Pour une carte SBC/Embarquée (ARM - ex: Orange Pi, Raspberry Pi) :
```
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
./Miniconda3-latest-Linux-aarch64.sh
```

Processus d'installation (commun) :

 Appuyez sur Entrée pour faire défiler la licence, puis tapez yes pour l'accepter.
 
 Validez l'emplacement d'installation par défaut en appuyant sur Entrée.
 
 Important : À la fin de l'installation, le script vous demande s'il doit exécuter conda init. Tapez impérativement yes.
 
 Enfin, pour que votre terminal prenne en compte l'installation immédiatement (sans avoir à vous déconnecter), tapez :

```
source ~/.bashrc
```

## 1. Création de l'environnement Conda
Ouvrez un terminal et créez un environnement dédié au nœud (ici, l'Oreille) avec une version de 

Python stable pour l'IA (Python 3.10 ou 3.11 est recommandé) :


```
conda create -n natacha_oreille python=3.11 -y
```


## 2. Activation et Installation


Activez ce nouvel environnement. Votre terminal affichera (natacha_oreille) au début de la ligne :

```
conda activate natacha_oreille
```

Placez-vous dans le dossier du module :

```
cd ~/Natacha-Project/modules/ear
```

L'astuce Conda pour l'audio : Plutôt que d'installer les dépendances système complexes via apt, laissez Conda gérer la compilation de PyAudio et de portaudio proprement :

```
conda install -c conda-forge pyaudio screen -y
```

Puis, installez le reste de vos librairies (MQTT, Faster-Whisper, etc.) :

```
pip install -r requirements.txt
```

## 3. Calibrage Matériel Audio (Uniquement Oreille)

Branchez votre casque/micro, assurez-vous d'être dans l'environnement Conda, et lancez l'utilitaire :

```
python3 setup_audio.py
```
Suivez les instructions pour générer automatiquement votre fichier .env contenant les identifiants de vos périphériques matériels.

Voici un exemple mon micro casque USB  se nomme   USB DONGLE : Audio

![Exemple d'execution de setup_audio.py](setup_audio.png)


## 4. Sécurité & Secrets

Pour des raisons de sécurité, les identifiants SSH ne sont pas inclus dans le dépôt. Pour configurer vos accès :

1. Allez dans le dossier `modules/ear/`.

2. Copiez le fichier d'exemple :

   ```bash
   cp secrets_natacha.py.example secrets_natacha.py
   ```

3. Modifiez `secrets_natacha.py` avec vos propres identifiants SSH et adresses IP.

## 5. Exécution & Automatisation (systemd avec Conda)


Vous pouvez tester le script manuellement :

```
python3 oreille_v1_30.py
```

Pour le lancement automatique au démarrage :
Avec Conda, le chemin vers l'exécutable Python est différent. Éditez votre fichier de service (ex: sudo nano /etc/systemd/system/natacha_oreille.service) :



## 6. Automatisation Robuste (Systemd + Screen)

Pour que le nœud démarre tout seul avec la machine tout en restant consultable, nous utilisons un service système couplé à screen.

Créez le fichier de service :

```
sudo nano /etc/systemd/system/natacha_oreille.service
```

Collez la configuration suivante (adaptez vieil par votre nom d'utilisateur) :
Ini, TOML

```
[Unit]
Description=Natacha - Nœud Oreille (Conda + Screen)
After=network.target sound.target

[Service]
User=vieil
WorkingDirectory=/home/vieil/Natacha-Project/modules/ear

Environment="XDG_RUNTIME_DIR=/run/user/1000"

ExecStart=/usr/bin/screen -DmS natacha_oreille /home/vieil/miniconda3/envs/natacha_oreille/bin/python3 oreille_v1_30.py

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Pour sortir de nano CTRL + o pour sauver puis CTRL + x pour sortir 

Activez et lancez le service :

```
sudo systemctl enable natacha_oreille.service
sudo systemctl start natacha_oreille.service
```

## 7. Monitoring au quotidien

Grâce à screen, le nœud tourne en tâche de fond mais reste accessible à tout moment :

```
screen -r natacha_oreille
```

Quitter l'affichage sans couper l'IA : Appuyez sur Ctrl+A puis D (Détacher).



## 8. Gstream  écoute de la synthèse vocale au casque 

On utilise le micro casque USB sur la carte ou ordinateur RYZEN 5 "oreille".
La carte reçoit un flux audio provenant de l'orangepi6plus la "Bouche".
Le casque USB va restituer la synthèse vocale provenant de la "Bouche"

⚙️ Optimisation du flux Audio (UDP)

Le pipeline GStreamer utilise un buffer de sécurité de 512 Ko (buffer-size=524288) pour éviter les craquements audio
sur le réseau Ethernet. Pour que ce buffer soit accepté par le système, vous devez augmenter la limite du noyau Linux :

Éditer la configuration système :

```
sudo nano /etc/sysctl.conf
```
Ajouter les lignes suivantes en bas du fichier :
Plaintext
```
net.core.rmem_max=524288
net.core.wmem_max=524288
```
    
Appliquer les changements :
```
sudo sysctl -p
```
    
Sans cette modification, GStreamer risque d'afficher un avertissement W: [pulsesink] pulseaudio.c: Protocol error ou des pertes de paquets UDP.
Avec ce réglage, le pipeline est "confortable" et peut gérer les 200ms de pré-chargement (min-threshold-time=200000000) sans que le noyau ne sature.

🎙️ Transcription Haute Fidélité : Faster-Whisper (Medium)   STT

Le module Oreille de Natacha s'appuie sur la technologie Faster-Whisper, une implémentation optimisée du modèle Whisper d'OpenAI utilisant
le moteur CTranslate2. Ce choix technique est au cœur de la réactivité du système.

Natacha a désormais une structure de déploiement digne des meilleurs serveurs de production.

Ton cluster est paré pour durer dans le temps ! 🚀



​Le projet  utilise  les accélérateurs matériels disponibles dans mon cas :

| Hardware | Backend Accelerators | Utilisation Optimale |
| :--- | :--- | :--- |
| **Intel Core** | Core I5 14400 | Cerveau / Oreille (Ultra-rapide) |
| **AMD Ryzen** | Ryzen 5500u (AVX-512) / ROCm | Oreille (Faster-Whisper) |
| **Rockchip (OPi 6+)** | RKNN (NPU) | Bouche TTS / Audio -Transfert UDP |



## 📡 Communication Inter-Machines

Natacha utilise une segmentation réseau pour garantir la stabilité :

* **Plan de Données (Ethernet)** : Flux audio et MQTT (Stabilité maximale).

* **Plan de Contrôle (Wi-Fi)** : Mises à jour et accès internet.

* **mDNS/Avahi** : Les machines se reconnaissent automatiquement (ex: `cerveaunatacha.local`).

## 📝 Roadmap

* [ ] Support complet des NPU Intel via OpenVINO.
* [ ] Intégration des modèles de vision pour l'Orange Pi 6+.
* [ ] Interface de monitoring temps réel du cluster.


## 💡 Pourquoi ce projet ?

Le projet Natacha démontre qu'il est possible de créer une IA domestique puissante en recyclant et en synchronisant du matériel varié, sans dépendre du Cloud, tout en conservant une latence de réponse "humaine".

*Développé par Thierry VIEIL - 2026*



