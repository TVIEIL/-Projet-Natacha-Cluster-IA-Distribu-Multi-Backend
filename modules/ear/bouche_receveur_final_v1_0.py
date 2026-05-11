# ==============================================================================
# PROJET NATACHA - NŒUD OREILLE (Ryzen 5)
# Script : bouche_receveur_final_v1.1.py
# Description : Réception du flux audio haute fidélité provenant de la Bouche
#                (Orange Pi 6 Plus) via Ethernet (UDP).
# ==============================================================================

import subprocess
import sys

# --- CONFIGURATION FORCEE ---
PORT_UDP = 5000
RATE = 22050
CHANNELS = 1
FORMAT = "S16LE"
SINK = "pulsesink"  # On force pulsesink ici

# Pipeline optimisé avec buffer de sécurité
pipeline = (
    f'gst-launch-1.0 udpsrc port={PORT_UDP} buffer-size=524288 ! ' # Augmente la socket UDP
    f'"audio/x-raw,rate={RATE},channels={CHANNELS},format={FORMAT},layout=interleaved" ! '
    f'queue max-size-buffers=0 max-size-time=0 max-size-bytes=0 ' 
    f'min-threshold-time=200000000 ! '  # Attend 200ms de données avant de démarrer
    f'rawaudioparse use-sink-caps=true ! '
    f'audioconvert ! audioresample ! '
    f'{SINK} buffer-time=200000 latency-time=10000' # Tampon PulseAudio stable
)

print(f"---")
print(f"✅ Receveur Natacha v1.1.0 opérationnel...")
print(f"🎧 Mode : Partage de flux (PulseAudio) | Port : {PORT_UDP}")
print(f"🔊 Format attendu : {RATE}Hz Mono (S16LE)")
print(f"---")
print("Appuyez sur Ctrl+C pour arrêter.")

try:
    # On utilise .run pour maintenir le pipeline ouvert
    subprocess.run(pipeline, shell=True)
except KeyboardInterrupt:
    print("\n🛑 Arrêt du receveur Natacha.")
    sys.exit(0)
