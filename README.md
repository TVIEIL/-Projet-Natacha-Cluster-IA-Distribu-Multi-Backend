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
## 🛠️ Installation & Déploiement

### 1. Pré-requis système & Matériel

* **OS** : Ubuntu 24.04+ ou Armbian (pour Rockchip).
* **Services** : Broker MQTT (Mosquitto) installé et actif sur le réseau.
* **Audio (Nœud Oreille)** : La capture audio via PyAudio nécessite des librairies système spécifiques. À installer en premier :

  ```bash
  sudo apt-get update
  sudo apt-get install python3-dev portaudio19-dev python3-venv
  ```

  Environnements Virtuels (Recommandé)

  Pour éviter les conflits, Natacha utilise un environnement virtuel par nœud. Exemple d'initialisation pour l'Oreille :
  
  ```bash
  cd modules/ear/
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

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



