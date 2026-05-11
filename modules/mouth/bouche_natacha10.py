import subprocess
import paho.mqtt.client as mqtt
import time
import os
import wave
import contextlib
import sys

# --- CONFIGURATION ---
# Broker sur le Core i5 14ème Gen
MQTT_BROKER = "192.168.1.100"   
# Oreille sur le RYZEN 5 5500U (Anciennement KickPi)
OREILLE_IP = "192.168.1.90"      
PIPER_EXE = "/home/tvieil/piper_bin/piper/piper"
MODEL_PATH = "/home/vieil/bouche_natacha/models/fr_FR-siwis-medium.onnx"
WAV_PATH = "/tmp/natacha_temp.wav"
TOPIC_ECOUTE = "natacha/reponse"

def get_wav_duration(fname):
    """Calcule la durée précise du fichier audio en secondes."""
    try:
        with contextlib.closing(wave.open(fname, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            return frames / float(rate)
    except Exception as e:
        print(f"⚠️ Erreur lecture durée WAV : {e}")
        return 0

def on_connect(client, userdata, flags, rc):
    print(f"✅ Connecté au Broker ({MQTT_BROKER}). Écoute : {TOPIC_ECOUTE}")
    client.subscribe(TOPIC_ECOUTE)

def on_message(client, userdata, msg):
    try:
        texte = msg.payload.decode("utf-8").strip()
        if not texte: return

        print(f"📦 Préparation de la phrase : {texte[:50]}...")
        # Nettoyage des caractères spéciaux pour éviter les erreurs Shell
        texte_clean = texte.replace('"', '').replace("'", "").replace("\n", " ")

        # 1. GÉNÉRATION DU FICHIER WAV (PIPER)
        gen_cmd = f'echo "{texte_clean}" | {PIPER_EXE} --model {MODEL_PATH} --output_file {WAV_PATH}'
        subprocess.run(gen_cmd, shell=True, check=True)

        if os.path.exists(WAV_PATH):
            # 2. CALCUL DE LA DURÉE ET ENVOI RÉSEAU
            duree = get_wav_duration(WAV_PATH)
            print(f"⏳ Durée : {duree:.2f}s. Envoi au Ryzen (.90)...")

            # Pipeline optimisé pour le récepteur Ryzen (S16LE / 22050Hz)
            send_cmd = (
                f'gst-launch-1.0 filesrc location={WAV_PATH} ! wavparse ! '
                f'audioconvert ! audioresample ! "audio/x-raw,rate=22050,channels=1,format=S16LE" ! '
                f'udpsink host={OREILLE_IP} port=5000'
            )
            
            # On utilise .run pour garantir que le fichier n'est pas supprimé avant l'envoi
            subprocess.run(send_cmd, shell=True)

            # 3. PAUSE DE SÉCURITÉ ET NETTOYAGE
            # On attend un tout petit peu après la fin du flux
            time.sleep(0.2)
            print("✨ Lecture terminée sur le Ryzen. Prêt.")
            
            if os.path.exists(WAV_PATH):
                os.remove(WAV_PATH)

    except Exception as e:
        print(f"⚠️ Erreur : {e}")

# --- INITIALISATION ---
# Utilisation de la version API compatible (Callback API version 1)
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
