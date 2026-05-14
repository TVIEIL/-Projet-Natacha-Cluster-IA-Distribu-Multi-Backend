#!/usr/bin/env python3
#
# Copyright 2026 Thierry VIEIL
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ==============================================================================
# PROJET NATACHA - MODULE BOUCHE
# ==============================================================================

# ==============================================================================
# PROJET : NATACHA - Assistant IA Distribué & Autonome
# MODULE : BOUCHE (Synthèse Vocale & Streaming Réseau)
# VERSION : 10.0
# AUTEUR : Thierry VIEIL
# DATE : 12 Mai 2026
# ENVIRONNEMENT : Ubuntu / Python 3 (Nœud Bouche)
# MATÉRIEL : Orange Pi 6 Plus
# ==============================================================================
#
# DESCRIPTION :
# Ce script gère la voix de Natacha. Il effectue :
# 1. RÉCEPTION : Écoute les réponses textuelles du Cerveau via MQTT.
# 2. SYNTHÈSE : Génère le fichier audio avec Piper TTS (Modèle Siwis).
# 3. STREAMING : Envoie le flux audio via GStreamer (UDP) vers le nœud Oreille.
# ==============================================================================

import subprocess
import paho.mqtt.client as mqtt
import time
import os
import wave
import contextlib
import sys
from dotenv import load_dotenv
from pathlib import Path


# ==============================================================================
# GESTION DYNAMIQUE DE LA CONFIGURATION (.env)
# ==============================================================================

def charger_ou_creer_env(chemin_complet):
    if not os.path.exists(chemin_complet):
        print(f"📁 Création du fichier .env à : {chemin_complet}")
        with open(chemin_complet, "w") as f:
            f.write("# CONFIGURATION NATACHA - BOUCHE\n")
            f.write("MQTT_BROKER=192.168.1.100\n")
            f.write("OREILLE_IP=192.168.1.90\n")
            # Utilisation de chemins génériques basés sur le home de l'utilisateur
            home = os.path.expanduser("~")
            f.write(f"PIPER_EXE={home}/piper_bin/piper/piper\n")
            f.write(f"MODEL_PATH={home}/bouche_natacha/models/fr_FR-siwis-medium.onnx\n")
            f.write("WAV_PATH=/tmp/natacha_temp.wav\n")
        print("✅ Fichier .env créé. Vérifiez les chemins à l'intérieur.")
    

# 1. On trouve d'abord le chemin (On trace le circuit)
base_path = Path(__file__).resolve().parent
env_path = base_path / ".env"

# 2. On vérifie/crée le fichier (On pose le composant)
charger_ou_creer_env(env_path)
    
# 3. On charge les données dans le script (On met sous tension)
load_dotenv(dotenv_path=env_path)

# --- CONFIGURATION (Extraite du .env) ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.100")
OREILLE_IP = os.getenv("OREILLE_IP", "192.168.1.90")
PIPER_EXE = os.getenv("PIPER_EXE")
MODEL_PATH = os.getenv("MODEL_PATH")
WAV_PATH = os.getenv("WAV_PATH", "/tmp/natacha_temp.wav")
TOPIC_ECOUTE = "natacha/reponse"

# ==============================================================================
# FONCTIONS TECHNIQUES
# ==============================================================================
def get_wav_duration(fname):
    """Calcule la durée précise du fichier audio en secondes."""
    try:
        if not os.path.exists(fname): return 0
        with contextlib.closing(wave.open(fname, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            return frames / float(rate)
    except Exception as e:
        print(f"⚠️ Erreur lecture durée WAV : {e}")
        return 0

# ==============================================================================
# GESTION DU RÉSEAU MQTT
# ==============================================================================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connecté au Broker ({MQTT_BROKER}). Écoute : {TOPIC_ECOUTE}")
        client.subscribe(TOPIC_ECOUTE)
    else:
        print(f"❌ Erreur de connexion au Broker (Code: {rc})")

def on_message(client, userdata, msg):
    try:
        texte = msg.payload.decode("utf-8").strip()
        if not texte: return

        print(f"📦 Préparation de la phrase : {texte[:50]}...")
        # Nettoyage des caractères spéciaux pour le Shell
        texte_clean = texte.replace('"', '').replace("'", "").replace("\n", " ")

        # 1. GÉNÉRATION DU FICHIER WAV (PIPER)
        if not os.path.exists(PIPER_EXE):
            print(f"❌ Erreur : Piper introuvable à {PIPER_EXE}")
            return

        gen_cmd = f'echo "{texte_clean}" | {PIPER_EXE} --model {MODEL_PATH} --output_file {WAV_PATH}'
        subprocess.run(gen_cmd, shell=True, check=True)

        if os.path.exists(WAV_PATH):
            # 2. CALCUL DE LA DURÉE ET ENVOI RÉSEAU (GStreamer)
            duree = get_wav_duration(WAV_PATH)
            print(f"⏳ Durée : {duree:.2f}s. Envoi vers Ryzen ({OREILLE_IP})...")

            # Pipeline optimisé pour le récepteur (S16LE / 22050Hz)
            send_cmd = (
                f'gst-launch-1.0 filesrc location={WAV_PATH} ! wavparse ! '
                f'audioconvert ! audioresample ! "audio/x-raw,rate=22050,channels=1,format=S16LE" ! '
                f'udpsink host={OREILLE_IP} port=5000'
            )
            
            # .run garantit la fin de l'envoi avant de passer à la suite
            subprocess.run(send_cmd, shell=True)

            # 3. PAUSE DE SÉCURITÉ ET NETTOYAGE
            time.sleep(0.2)
            print("✨ Lecture terminée sur le Ryzen. Prêt.")
            
            if os.path.exists(WAV_PATH):
                os.remove(WAV_PATH)

    except Exception as e:
        print(f"⚠️ Erreur traitement message : {e}")

# ==============================================================================
# LANCEMENT
# ==============================================================================
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    print("👄 Bouche de Natacha opérationnelle (Orange Pi 6 Plus).")
    print(f"🔗 Lien réseau vers Ryzen : {OREILLE_IP}:5000")
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_forever()
except KeyboardInterrupt:
    print("\n👋 Fermeture de la bouche.")
    sys.exit(0)
except Exception as e:
    print(f"❌ Erreur critique : {e}")
