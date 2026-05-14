# ==============================================================================
# PROJET NATACHA - NŒUD OREILLE (Ryzen 5)
# Script : bouche_receveur_final_v1_0.py (v1.0-SR)
# ==============================================================================

import subprocess
import sys
import os
from dotenv import load_dotenv
import re

# --- CHARGEMENT DE LA CONFIGURATION ---
load_dotenv()

# --- CONFIGURATION DU FLUX (Ce qui vient de l'Orange Pi) ---
# On garde 22050 Hz car c'est la fréquence d'émission de la Bouche
STREAM_RATE = 22050 
PORT_UDP = 5000
CHANNELS = 1
FORMAT = "S16LE"

# --- CONFIGURATION DE SORTIE (Ton matériel Ryzen) ---
# On récupère le RATE matériel de ton .env (48000 Hz) pour informer GStreamer
HW_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", 48000))
device_env = os.getenv("SPEAKER_DEVICE_NAME", "")


# On cherche le (hw:X,Y) dans la chaîne du .env
match = re.search(r'\((hw:\d+,\d+)\)', device_env)

if match:
    alsa_device = match.group(1) # Récupère 'hw:2,0'
    SINK = f"alsasink device={alsa_device}"
    print(f"✅ Sortie forcée sur le matériel : {alsa_device}")
else:
    SINK = "pulsesink"
    print("⚠️ Matériel spécifique non trouvé dans le .env, repli sur pulsesink.")

# Pipeline intelligent : 
# 1. Il reçoit en 22050 Hz (le flux réseau)
# 2. Il convertit et ré-échantillonne (audioresample) vers la sortie PulseAudio
pipeline = (
    f'gst-launch-1.0 udpsrc port={PORT_UDP} buffer-size=524288 ! '
    f'"audio/x-raw,rate={STREAM_RATE},channels={CHANNELS},format={FORMAT},layout=interleaved" ! '
    f'queue max-size-buffers=0 max-size-time=0 max-size-bytes=0 ' 
    f'min-threshold-time=200000000 ! ' 
    f'rawaudioparse use-sink-caps=true ! '
    f'audioconvert ! '
    f'audioresample ! ' # <-- C'est lui qui fait le pont entre 22050 et 48000 Hz
    f'{SINK} buffer-time=200000 latency-time=10000'
)

print(f"---")
print(f"✅ Receveur Natacha v1.0 (Mode Résilient) ...")
print(f"📡 Réception réseau : {STREAM_RATE} Hz")
print(f"🔊 Sortie matérielle (via .env) : {HW_RATE} Hz")
print(f"---")

try:
    subprocess.run(pipeline, shell=True)
except KeyboardInterrupt:
    print("\n🛑 Arrêt du receveur.")
    sys.exit(0)
