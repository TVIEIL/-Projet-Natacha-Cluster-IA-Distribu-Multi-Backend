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
# PROJET NATACHA - MODULE GSTREAM FLUX AUDIO SYNTHESE VOCALE VERS MICRO-CASQUE
# ==============================================================================

# ==============================================================================
# PROJET NATACHA - NŒUD OREILLE (Ryzen 5)
# Script : bouche_receveur_final_v1_0.py (v1.0-SR)
# ==============================================================================

import subprocess
import sys
import os
from dotenv import load_dotenv
import re
import threading
import shutil # Pour vérifier proprement la présence des commandes
import time

def forcer_audio_systeme():
    """ 
    Failsafe : Tente de démueter le son via PulseAudio (Desktop) 
    ou via AMIXER (Server pur).
    """
    try:
        time.sleep(2)
        
        # --- CAS 1 : Système avec PulseAudio (Ubuntu Desktop) ---
        if shutil.which("pactl"):
            os.system("pactl set-sink-mute @DEFAULT_SINK@ false > /dev/null 2>&1")
            os.system("pactl set-sink-volume @DEFAULT_SINK@ 50% > /dev/null 2>&1")
            print("🔊 Failsafe : PulseAudio démueté (50%).")

        # --- CAS 2 : Système Server pur (ALSA direct) ---
        if shutil.which("amixer"):
            # On tente de démueter le Master général
            os.system("amixer sset Master unmute > /dev/null 2>&1")
            os.system("amixer sset Master 50% > /dev/null 2>&1")
            
            # Cas spécifique HDMI (ton cas sur le Ryzen)
            # On force l'activation des switchs numériques IEC958
            os.system("amixer -c 0 sset IEC958 on > /dev/null 2>&1")
            os.system("amixer -c 0 sset IEC958,1 on > /dev/null 2>&1")
            print("🔊 Failsafe : ALSA/HDMI démueté via amixer.")

    except Exception as e:
        # On reste discret en cas d'erreur pour ne pas bloquer le démarrage
        pass

# Lancement du gardien en arrière-plan
thread_son = threading.Thread(target=forcer_audio_systeme, daemon=True)
thread_son.start()

# --- RÉGLAGE DU VOLUME ---
# 1.0 = 100% (volume normal)
# 0.5 = 50%
# 0.2 = 20% (ce que je te conseille pour commencer)
NIVEAU_SONORE = 0.5

# --- CHARGEMENT DE LA CONFIGURATION ---
load_dotenv()

# --- CONFIGURATION DU FLUX (Ce qui vient de l'Orange Pi) ---
# On garde 22050 Hz car c'est la fréquence d'émission de la Bouche
STREAM_RATE = 22050 
PORT_UDP = 5000
CHANNELS = 1
FORMAT = "S16LE"

# --- CONFIGURATION DE SORTIE (Mon matériel Ryzen) ---
# On récupère le RATE matériel de ton .env (48000 Hz) pour informer GStreamer
HW_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", 48000))
device_env = os.getenv("SPEAKER_DEVICE_NAME", "")


# On cherche le (hw:X,Y) dans la chaîne du .env
match = re.search(r'\((hw:\d+,\d+)\)', device_env)

if match:
    alsa_device = match.group(1) # Récupère 'hw: -,-
    SINK = f"alsasink device={alsa_device}"
    print(f"✅ Sortie forcée sur le matériel : {alsa_device}")
else:
    SINK = "pulsesink"
    print("⚠️ Matériel spécifique non trouvé dans le .env, repli sur pulsesink.")

# Pipeline intelligent : 
# 1. Il reçoit en 22050 Hz (le flux réseau)
# 2. Il convertit et ré-échantillonne (audioresample) vers la sortie PulseAudio
#pipeline = (
#    f'gst-launch-1.0 udpsrc port={PORT_UDP} buffer-size=524288 ! '
#    f'"audio/x-raw,rate={STREAM_RATE},channels={CHANNELS},format={FORMAT},layout=interleaved" ! '
#    f'queue max-size-buffers=0 max-size-time=0 max-size-bytes=0 ' 
#    f'min-threshold-time=200000000 ! ' 
#    f'rawaudioparse use-sink-caps=true ! '
#    f'audioconvert ! '
#    f'audioresample ! ' # <-- C'est lui qui fait le pont entre 22050 et 48000 Hz
#    f'{SINK} buffer-time=200000 latency-time=10000'
#)

pipeline = (
    f'gst-launch-1.0 udpsrc port={PORT_UDP} buffer-size=524288 ! '
    f'"audio/x-raw,rate={STREAM_RATE},channels={CHANNELS},format={FORMAT},layout=interleaved" ! '
    # Ta file d'attente anti-jitter (ne surtout pas l'enlever !)
    f'queue max-size-buffers=0 max-size-time=0 max-size-bytes=0 ' 
    f'min-threshold-time=200000000 ! ' 
    f'rawaudioparse use-sink-caps=true ! '
    f'audioconvert ! '
    f'audioresample ! ' # <--- Le pont 22k vers 48k est bien là
    f'volume volume={NIVEAU_SONORE} ! ' # Le réglage de puissance
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
