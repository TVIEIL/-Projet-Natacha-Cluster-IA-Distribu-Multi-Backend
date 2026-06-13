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
# PROJET NATACHA - MODULE OREILLE
# ==============================================================================

# ==============================================================================
# PROJET NATACHA - MODULE OREILLE (v1.30-SR)
# ==============================================================================
# Rôle : Capture audio haute fidélité, transcription IA et pilotage du cluster.
# Hardware cible : AMD Ryzen (Nœud "Oreille")
# 
# Fonctionnalités :
#   - Capture via configuration dynamique (.env)
#   - Transcription locale via Faster-Whisper (Modèle Medium / int8).
#   - Analyse syntaxique d'intentions (Relance, Arrêt, Diagnostic).
#   - Pilotage distant du cluster (Cerveau i5 / Bouche OPi 6+) via SSH & MQTT.
# ==============================================================================



import os, time, subprocess, paramiko, pyaudio, socket, numpy as np
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from faster_whisper import WhisperModel
from dotenv import load_dotenv  
from pathlib import Path
import sys
from contextlib import contextmanager

os.environ['PYTHONUNBUFFERED'] = '1'
os.environ['AUDIODEV'] = 'hw:4' 

# On trouve le chemin du script lui-même
base_path = Path(__file__).resolve().parent
env_path = base_path / ".env"
reussite_question = False
reussite_statut = False

# On charge le .env
load_dotenv(dotenv_path=env_path)

# --- IMPORT DES SECRETS ---
try:
    from secrets_natacha import CREDS, OREILLE_IP, CERVEAU_IP, BOUCHE_IP, MQTT_IP
except ImportError:
    print("❌ Erreur : Le fichier secrets_natacha.py est manquant !")
    exit(1)
    
# --- CONFIGURATION MATÉRIELLE ---
MIC_USB_ID = os.getenv("MIC_USB_ID")
MIC_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", 48000))
CHANNELS = 2
CHUNK = int(MIC_RATE / 10)
SILENCE_THRESHOLD = 0.005
MAX_SILENCE_CHUNKS = 25

@contextmanager
def ignore_stderr():
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(sys.stderr.fileno())
    os.dup2(devnull, sys.stderr.fileno())
    try:
        yield
    finally:
        os.dup2(old_stderr, sys.stderr.fileno())
        os.close(devnull)
        os.close(old_stderr)

def connecter_mqtt():
    try:
        print(f"🔗 Tentative de connexion au broker MQTT : {MQTT_IP}...")
        mqtt_client.connect(MQTT_IP, 1883, keepalive=60)
        mqtt_client.loop_start() 
        print("✅ Connexion MQTT établie avec succès.")
        return True
    except Exception as e:
        print(f"❌ Erreur de connexion MQTT vers {MQTT_IP} : {e}")
        return False

def get_hw_index_by_usb_id(target_usb_id):
    """ Recherche via l'ID matériel pour garantir la stabilité """
    try:
        lsusb_out = subprocess.check_output("lsusb", shell=True).decode()
        if target_usb_id not in lsusb_out:
            return None
    except:
        return None
    
    p = pyaudio.PyAudio()
    # On retourne l'index 4 par défaut car c'est celui validé par setup_audio.py
    # Si besoin, on pourrait itérer pour confirmer
    p.terminate()
    return 4 

        
def envoyer_mqtt(topic, message):
    if mqtt_client.is_connected():
        # publish() retourne un objet MQTTMessageInfo
        result = mqtt_client.publish(topic, message, qos=1, retain=False)
        
        # rc == 0 signifie MQTT_ERR_SUCCESS
        success = (result.rc == mqtt.MQTT_ERR_SUCCESS)
        
        if success:
            print(f"✅ MQTT Sent to {topic}: {message}")
            return True
        else:
            print(f"❌ MQTT Publish failed with error code: {result.rc}")
            return False
    else:
        print(f"🚫 Offline - Tentative de reconnexion...")
        connecter_mqtt()
        # On retourne False car l'envoi a échoué à cause de la déconnexion
        return False

def execute_remote_command(ip, user, password, command):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=user, password=password, timeout=5)
        ssh.exec_command(f"echo {password} | sudo -S {command}")
        ssh.close()
        return True
    except: return False

def check_health(ip, port):
    target_ip = "127.0.0.1" if ip == OREILLE_IP else ip
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        res = sock.connect_ex((target_ip, port))
        sock.close()
        return "opérationnelle " if res == 0 else "hors ligne "
    except: return "hors ligne "

# --- INITIALISATION ---
mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION2)
connecter_mqtt()

input_idx = get_hw_index_by_usb_id(MIC_USB_ID)
if input_idx is None:
    print(f"❌ Erreur : Impossible de trouver le micro avec ID {MIC_USB_ID}")
    sys.exit(1)

print(f"📥 Chargement de Whisper Medium (Rate cible: {MIC_RATE} Hz)...")
model = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=12, num_workers=1)

p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=MIC_RATE,
                input=True, input_device_index=input_idx, frames_per_buffer=CHUNK)

print(f"🎤 Natacha v1.30-SR (Rate: {MIC_RATE}Hz). Je t'écoute sur l'index {input_idx}...")

audio_buffer = []
silence_counter = 0

KEYWORDS_NOM = ["natacha", "natasha", "natascha", "tante"]
ACT_ANALYSE = ["analyse", "diagnostic", "rapport", "santé", "statut", "état"]
SUJ_ANALYSE = ["fonctionnement", "système", "marche", "opérationnel"]
ACT_RELANCE = ["redémarrage", "relance", "relancer", "restart", "reboot"]
SUJ_RELANCE = ["services", "logiciels", "système", "tout", "programmes", "natacha"]
ACT_ARRET = ["arrêt", "arret", "arré", "arre", "arrête", "éteindre", "stop", "halt"]
SUJ_ARRET = ["complet", "complé", "compliquer", "comblé", "total", "système", "assis"]

try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_raw = np.frombuffer(data, dtype=np.int16)
        step = int(MIC_RATE / 16000)
        audio_mono_float = audio_raw[::CHANNELS].astype(np.float32) / 32768.0
        
        if np.sqrt(np.mean(audio_mono_float**2)) > SILENCE_THRESHOLD:
            audio_buffer.append(audio_mono_float)
            silence_counter = 0
            print(".", end="", flush=True)
        else:
            if audio_buffer:
                silence_counter += 1
                if silence_counter > MAX_SILENCE_CHUNKS:
                    print("\n🔍 Analyse...")
                    full_audio = np.concatenate(audio_buffer)
                    audio_16k = full_audio[::step] 
                    segments, _ = model.transcribe(audio_16k, beam_size=1, language="fr", vad_filter=True)
                    for segment in segments:
                        raw_text = segment.text.strip()
                        text = raw_text.lower().replace(',', ' ').replace('.', ' ')
                        print(f"✨ Entendu : {raw_text}")
                        if any(nom in text for nom in KEYWORDS_NOM):
                            if any(act in text for act in ACT_RELANCE) and any(suj in text for suj in SUJ_RELANCE):
                                time.sleep(8)
                                cmd1 = "XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user restart natacha-brain.service"
                                execute_remote_command(CERVEAU_IP, CREDS["cerveau"]["user"], CREDS["cerveau"]["pass"], cmd1)
                                time.sleep(8)
                                execute_remote_command(CERVEAU_IP, CREDS["cerveau"]["user"], CREDS["cerveau"]["pass"], "systemctl --user restart cerveau_natacha.service")
                                time.sleep(8)
                                execute_remote_command(BOUCHE_IP, CREDS["bouche"]["user"], CREDS["bouche"]["pass"], "systemctl --user restart bouche_natacha.service")
                                time.sleep(8)
                                execute_remote_command(MQTT_IP, CREDS["mqtt"]["user"], CREDS["mqtt"]["pass"], "sudo /usr/bin/docker-compose -f /home/vieil/mqtt/docker-compose.yml restart")
                                time.sleep(8)
                                os.system(f"echo {CREDS['oreille']['pass']} | sudo systemctl  restart gstream_natacha.service")
                                time.sleep(8)
                                os.system(f"echo {CREDS['oreille']['pass']} | systemctl --user restart oreille_natacha.service")
                                time.sleep(8)
                            elif any(act in text for act in ACT_ARRET) and any(suj in text for suj in SUJ_ARRET):
                                reussite_question = envoyer_mqtt("natacha/reponse", "Extinction en cours.")
                                os.system(f"echo {CREDS['oreille']['pass']} | sudo -S halt")
                            elif any(act in text for act in ACT_ANALYSE) and any(suj in text for suj in SUJ_ANALYSE):
                                reussite_question = envoyer_mqtt("natacha/reponse", f"Le serveur de communication  mosquitto est  {check_health(CERVEAU_IP, 1883)}.")
                            elif len(text) > 3:
                                # On réaffecte ici, cela garantit que tu testes le résultat de l'envoi présent
                                reussite_question = envoyer_mqtt("natacha/question", raw_text) 

                                if reussite_question:
                                    reussite_statut = envoyer_mqtt("natacha/status", "traitement en cours")
                                    time.sleep(5)
                                    if reussite_statut:
                                        print("✅ Question transmise et statut 'traitement en cours' activé.")
                                    else:
                                        print("⚠️ Question envoyée, mais échec de transmission du statut.")
                                else:
                                    print("❌ Échec de l'envoi de la question.")
                    audio_buffer, silence_counter = [], 0
except KeyboardInterrupt:
    print("\n🛑 Fin du programme.")
finally:
    if 'stream' in locals():
        stream.close()
    p.terminate()

