# -Projet-Natacha-Cluster-IA-Distribu-Multi-Backend

![Schéma de l'Architecture Natacha](architecture-natacha.png)

Natacha est un assistant personnel modulaire conçu pour fonctionner sur un cluster de machines hétérogènes. Contrairement aux solutions monolithiques, Natacha fragmente l'intelligence (Cerveau, Oreille, Bouche) pour exploiter le meilleur de chaque architecture matérielle (Intel Core/Ultra, AMD Ryzen, Rockchip RK3588, NVIDIA Jetson).




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
Ouvrez un terminal et créez un environnement dédié au nœud (ici, l'Oreille) avec une version de Python stable pour l'IA (Python 3.10 ou 3.11 est recommandé) :


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
conda install -c conda-forge pyaudio -y
```

Puis, installez le reste de vos librairies (MQTT, Faster-Whisper, etc.) :

```
pip install -r requirements.txt
```

## 3. Calibrage Matériel Audio (Uniquement Oreille)

Branchez votre casque/micro, assurez-vous d'être dans l'environnement Conda, et lancez l'utilitaire :
Bash

python3 setup_audio.py

Suivez les instructions pour générer automatiquement votre fichier .env contenant les identifiants de vos périphériques matériels.
4. Exécution & Automatisation (systemd avec Conda)

Vous pouvez tester le script manuellement :
Bash

python3 oreille_v1_30.py

Pour le lancement automatique au démarrage :
Avec Conda, le chemin vers l'exécutable Python est différent. Éditez votre fichier de service (ex: sudo nano /etc/systemd/system/natacha_oreille.service) :



​Le projet détecte et utilise automatiquement les accélérateurs matériels disponibles :

| Hardware | Backend Accelerators | Utilisation Optimale |
| :--- | :--- | :--- |
| **Intel Core Ultra** | OpenVINO (GPU Arc / NPU) | Cerveau / Oreille (Ultra-rapide) |
| **AMD Ryzen** | CPU (AVX-512) / ROCm | Oreille (Faster-Whisper) |
| **Rockchip (OPi 6+)** | RKNN (NPU) | Bouche / Micro-services |
| **NVIDIA Jetson** | CUDA / TensorRT | Vision / Cerveau |


​2. Configuration du Backend

​Éditez le fichier .env pour définir vos capacités matérielles :

# Sélection du moteur d'inférence

```
STT_BACKEND='openvino'
LLM_BACKEND='llama-cpp'
```

### 3. Sécurité & Secrets

Pour des raisons de sécurité, les identifiants SSH ne sont pas inclus dans le dépôt. Pour configurer vos accès :

1. Allez dans le dossier `modules/ear/`.

2. Copiez le fichier d'exemple :

   ```bash
   cp secrets_natacha.py.example secrets_natacha.py
   ```

3. Modifiez `secrets_natacha.py` avec vos propres identifiants SSH et adresses IP.

### 4. Lancement des Services

Chaque nœud peut être lancé indépendamment. Exemple pour lancer l'Oreille (version 1.30-SR) sur un Ryzen :


```bash
python3 modules/ear/oreille_v1_30.py
```

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



