# -Projet-Natacha-Cluster-IA-Distribu-Multi-Backend
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

🛠️ Installation & Déploiement

​1. Pré-requis système

​OS : Ubuntu 24.04+ ou Armbian (pour Rockchip).
​Services : Broker MQTT (Mosquitto) installé sur le nœud "Cerveau".


​Le projet détecte et utilise automatiquement les accélérateurs matériels disponibles :

Hardware Backend Accelerators Utilisation Optimale
Intel Core Ultra OpenVINO (GPU Arc / NPU) Cerveau / Oreille Ultra-rapide
AMD Ryzen CPU (AVX-512) / ROCm Oreille (Faster-Whisper)
Rockchip (OPi 6+) RKNN (NPU) Bouche / Micro-services
NVIDIA Jetson CUDA / TensorRT Vision / Cerveau


​2. Configuration du Backend

​Éditez le fichier .env pour définir vos capacités matérielles :

# Sélection du moteur d'inférence
STT_BACKEND="openvino"  # Options: cpu, cuda, openvino, rknn
LLM_BACKEND="llama-cpp" # Options: ollama, llama-cpp, vllm


3. Lancement des Services

​Chaque nœud peut être lancé indépendamment via systemd ou Docker :

# Exemple pour lancer l'Oreille sur un Ryzen
python3 modules/ear/main.py --device cpu --threads 12

📡 Communication Inter-Machines

​Natacha utilise une segmentation réseau pour garantir la stabilité :
​Plan de Données (Ethernet) : Flux audio et MQTT (Stabilité maximale).
​Plan de Contrôle (Wi-Fi) : Mises à jour et accès internet.
​Les machines se reconnaissent automatiquement via mDNS/Avahi (ex: cerveaunatacha.local).

​📝 Roadmap

​[ ] Support complet des NPU Intel via OpenVINO.
​[ ] Intégration des modèles de vision pour l'Orange Pi 6+.
​[ ] Interface de monitoring temps réel du cluster.

​💡 Pourquoi ce projet ?

​Le projet Natacha démontre qu'il est possible de créer une IA domestique puissante en recyclant et en synchronisant du matériel varié, sans dépendre du Cloud, tout en conservant une latence de réponse "humaine".


