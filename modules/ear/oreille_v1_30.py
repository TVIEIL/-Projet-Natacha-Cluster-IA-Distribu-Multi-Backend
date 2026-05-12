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
from dotenv import load_dotenv  # <-- AJOUT : Pour lire le .env

# --- CHARGEMENT DE LA CONFIGURATION DYNAMIQUE ---
load_dotenv()  # Charge le fichier .env généré par setup_audio.py

# --- IMPORT DES SECRETS ---
try:
    from secrets_natacha import CREDS, OREILLE_IP, CERVEAU_IP, BOUCHE_IP
except ImportError:
    print("❌ Erreur : Le fichier secrets_natacha.py est manquant !")
    exit(1)

# --- CONFIGURATION MATÉRIELLE DYNAMIQUE ---
# On récupère les valeurs du .env avec des valeurs de secours (defaults) au cas où
TARGET_MIC_NAME = os.getenv("MIC_DEVICE_NAME", "USB DONGLE")
MIC_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", 48000))
CHANNELS = 2  # Ton dongle semble préférer le stéréo (2 canaux) pour le flux
CHUNK = int(MIC_RATE / 10) # Buffer de 100ms proportionnel au RATE

# Paramètres de détection de silence
SILENCE_THRESHOLD = 0.005  
MAX_SILENCE_CHUNKS = 25    

# Initialisation du client MQTT
mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION2)

def connecter_mqtt():
    try:
        mqtt_client.connect(CERVEAU_IP, 1883, keepalive=60)
        mqtt_client.loop_start() 
        return True
    except: return False

def envoyer_mqtt(topic, message):
    if mqtt_client.is_connected():
        mqtt_client.publish(topic, message)
    else: print(f"🚫 Offline - {topic} : {message}")

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

print(f"📥 Chargement de Whisper Medium (Rate cible: {MIC_RATE} Hz)...")
model = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=12, num_workers=1)

p = pyaudio.PyAudio()
input_idx = None

# Recherche de l'index par nom (Flexible : cherche si le nom du .env est contenu dans le nom ALSA)
for i in range(p.get_device_count()):
    dev_info = p.get_device_info_by_index(i)
    if TARGET_MIC_NAME.upper() in dev_info['name'].upper():
        input_idx = i
        break

if input_idx is None:
    print(f"❌ Erreur : Impossible de trouver le périphérique '{TARGET_MIC_NAME}'")
    p.terminate()
    exit(1)

connecter_mqtt()
stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=MIC_RATE,
                input=True, input_device_index=input_idx, frames_per_buffer=CHUNK)

print(f"🎤 Natacha v1.30-SR (Rate: {MIC_RATE}Hz). Je t'écoute sur l'index {input_idx}...")

audio_buffer = []
silence_counter = 0

# Mots clés
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
        
        # Downsampling & Mono conversion
        # On prend un canal sur deux (::CHANNELS) et on divise par 3 pour passer de 48k à 16k si besoin
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
                    
                    # Resampling final à 16kHz pour Whisper
                    audio_16k = full_audio[::step] 
                    
                    segments, _ = model.transcribe(audio_16k, beam_size=1, language="fr", vad_filter=True)
                    
                    for segment in segments:
                        raw_text = segment.text.strip()
                        text = raw_text.lower().replace(',', ' ').replace('.', ' ')
                        print(f"✨ Entendu : {raw_text}")
                        cond_nom = any(nom in text for nom in KEYWORDS_NOM)
                        
                        if cond_nom:
                            # CAS 1 : RELANCE GLOBALE
                            if any(act in text for act in ACT_RELANCE) and any(suj in text for suj in SUJ_RELANCE):
                                print("🔄 Relance globale...")
                                envoyer_mqtt("natacha/reponse", "Relance Natacha en cours.")
                                time.sleep(8)
                                execute_remote_command(CERVEAU_IP, CREDS["cerveau"]["user"], CREDS["cerveau"]["pass"], "systemctl restart mosquitto.service")
                                execute_remote_command(CERVEAU_IP, CREDS["cerveau"]["user"], CREDS["cerveau"]["pass"], "systemctl restart natacha-brain.service")
                                execute_remote_command(CERVEAU_IP, CREDS["cerveau"]["user"], CREDS["cerveau"]["pass"], "systemctl restart cerveau_natacha.service")
                                execute_remote_command(CERVEAU_IP, CREDS["cerveau"]["user"], CREDS["cerveau"]["pass"], "systemctl restart kiwix.service")
                                execute_remote_command(BOUCHE_IP, CREDS["bouche"]["user"], CREDS["bouche"]["pass"], "systemctl restart bouche_de_natacha.service") 
                                cmd_oreille_gst = "killall -9 gst-launch-1.0 ; systemctl restart gstream-natacha.service"
                                execute_remote_command(OREILLE_IP, CREDS["oreille"]["user"], CREDS["oreille"]["pass"], cmd_oreille_gst)
                                execute_remote_command(OREILLE_IP, CREDS["oreille"]["user"], CREDS["oreille"]["pass"], "systemctl restart oreille_natacha.service.service")                                
                                                
                            # CAS 2 : ARRÊT TOTAL
                            elif any(act in text for act in ACT_ARRET) and any(suj in text for suj in SUJ_ARRET):
                                print("🛑 Arrêt reçu !")
                                envoyer_mqtt("natacha/reponse", "Extinction en cours, au revoir Thierry.")
                                time.sleep(8)
                                execute_remote_command(CERVEAU_IP, CREDS["cerveau"]["user"], CREDS["cerveau"]["pass"], "halt")
                                execute_remote_command(BOUCHE_IP, CREDS["bouche"]["user"], CREDS["bouche"]["pass"], "halt")
                                os.system(f"echo {CREDS['oreille']['pass']} | sudo -S halt")

                            # CAS 3 : RAPPORT DE SANTÉ
                            elif any(act in text for act in ACT_ANALYSE) and any(suj in text for suj in SUJ_ANALYSE):
                                rapport = f"Santé : MQTT {check_health(CERVEAU_IP, 1883)}."
                                envoyer_mqtt("natacha/reponse", rapport)

                            # CAS 4 : QUESTION AU LLM
                            elif len(text) > 3:
                                try:
                                    print("Envoi d'une question au cerveau.\n")
                                    envoyer_mqtt("natacha/question", raw_text)
                                    print("✅ MQTT : Question envoyée.")
                                except Exception as e:
                                    print(f"❌ Erreur MQTT : {e}")

                    audio_buffer, silence_counter = [], 0

except KeyboardInterrupt:
    print("\n🛑 Fin du programme.")
finally:
    if 'stream' in locals():
        stream.close()
    p.terminate()
