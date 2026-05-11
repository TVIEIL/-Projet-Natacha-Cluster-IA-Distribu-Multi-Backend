# ==============================================================================
# PROJET : NATACHA
# MODULE : Utilitaire de Calibrage Audio (setup_audio.py)
# AUTEUR : Thierry VIEIL
# DESCRIPTION : 
# Ce script permet d'identifier les périphériques audio (USB) par leur NOM plutôt
# que par leur INDEX. Il réalise un test d'écho (boucle locale) et génère le 
# fichier .env nécessaire au fonctionnement résilient de l'Oreille et de la Bouche.
# ==============================================================================

import pyaudio
import time

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 22050
CHUNK = 1024
RECORD_SECONDS = 3

p = pyaudio.PyAudio()

def lister_peripheriques():
    print("\n--- 🎤 ENTRÉES DISPONIBLES (Micro) ---")
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get('maxInputChannels') > 0:
            print(f"Index [{i}] : {dev.get('name')}")

    print("\n--- 🔊 SORTIES DISPONIBLES (Casque) ---")
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get('maxOutputChannels') > 0:
            print(f"Index [{i}] : {dev.get('name')}")

def test_echo(input_idx, output_idx):
    print(f"\n🎙️ Enregistrement de {RECORD_SECONDS} secondes... Parlez maintenant !")
    try:
        stream_in = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, 
                           input=True, input_device_index=input_idx, frames_per_buffer=CHUNK)
        frames = []
        for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            frames.append(stream_in.read(CHUNK, exception_on_overflow=False))
            
        stream_in.stop_stream()
        stream_in.close()
        print("✅ Enregistrement terminé.")
        
        print("🎧 Lecture dans le casque...")
        stream_out = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, 
                            output=True, output_device_index=output_idx, frames_per_buffer=CHUNK)
        for data in frames:
            stream_out.write(data)
            
        stream_out.stop_stream()
        stream_out.close()
        print("✅ Lecture terminée.")
        return True
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False

# --- DÉROULEMENT ---
print("="*50)
print("🛠️ UTILITAIRE DE CALIBRAGE AUDIO - PROJET NATACHA")
print("="*50)

lister_peripheriques()

try:
    in_idx = int(input("\n👉 Entrez l'Index de votre MICROPHONE : "))
    out_idx = int(input("👉 Entrez l'Index de votre CASQUE : "))
    
    succes = test_echo(in_idx, out_idx)
    
    if succes:
        if input("\nAvez-vous entendu votre voix correctement ? (o/n) : ").lower() == 'o':
            # ON RÉCUPÈRE LES NOMS ICI
            nom_in = p.get_device_info_by_index(in_idx).get('name')
            nom_out = p.get_device_info_by_index(out_idx).get('name')
            
            print("💾 Génération du fichier .env en cours...")
            with open(".env", "w") as env_file:
                env_file.write(f"MIC_DEVICE_NAME={nom_in}\n")
                env_file.write(f"SPEAKER_DEVICE_NAME={nom_out}\n")
                env_file.write(f"AUDIO_SAMPLE_RATE={RATE}\n")
            print("🎉 Terminé ! Les NOMS de vos périphériques ont été sauvegardés.")
except ValueError:
    print("❌ Erreur de saisie.")
finally:
    p.terminate()
