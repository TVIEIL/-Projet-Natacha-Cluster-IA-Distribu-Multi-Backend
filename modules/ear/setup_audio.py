
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
# PROJET NATACHA - MODULE SETUP AUDIO
# ==============================================================================

# ==============================================================================
# PROJET : NATACHA
# MODULE : Utilitaire de Calibrage Audio Robuste (setup_audio.py)
# DESCRIPTION : Identification, scan de fréquences et gestion d'erreurs de saisie.
# ==============================================================================

import pyaudio
import os

# --- PARAMÈTRES ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
CHUNK = 1024
RECORD_SECONDS = 3

p = pyaudio.PyAudio()

def obtenir_peripheriques_valides():
    """ Retourne deux listes contenant les index valides pour In et Out """
    inputs = []
    outputs = []
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get('maxInputChannels') > 0:
            inputs.append(i)
        if dev.get('maxOutputChannels') > 0:
            outputs.append(i)
    return inputs, outputs

def lister_peripheriques(inputs, outputs):
    """ Affiche les périphériques disponibles """
    print("\n--- 🎤 ENTRÉES DISPONIBLES (Micro) ---")
    for i in inputs:
        print(f"Index [{i}] : {p.get_device_info_by_index(i).get('name')}")

    print("\n--- 🔊 SORTIES DISPONIBLES (Casque) ---")
    for i in outputs:
        print(f"Index [{i}] : {p.get_device_info_by_index(i).get('name')}")

def saisir_index_valide(liste_valide, message):
    """ Force l'utilisateur à saisir un index correct présent dans la liste """
    while True:
        try:
            choix = int(input(message))
            if choix in liste_valide:
                return choix
            else:
                print(f"⚠️ Erreur : L'index {choix} n'est pas dans la liste ci-dessus. Recommencez.")
        except ValueError:
            print("⚠️ Erreur : Veuillez entrer un numéro (chiffre uniquement).")

def scanner_frequences(input_idx, output_idx):
    """ Teste les fréquences acceptées par le matériel """
    freq_standards = [16000, 22050, 44100, 48000]
    valides = []
    print("\n🔍 Analyse des capacités matérielles...")
    for f in freq_standards:
        try:
            if p.is_format_supported(rate=f, 
                                     input_device=input_idx, input_channels=CHANNELS, input_format=FORMAT,
                                     output_device=output_idx, output_channels=CHANNELS, output_format=FORMAT):
                valides.append(f)
                print(f"  ✅ {f} Hz : OK")
        except Exception:
            print(f"  ❌ {f} Hz : Non supporté")
    return valides

def test_echo(input_idx, output_idx, rate_test):
    """ Enregistre et rejoue le son """
    print(f"\n🎙️ Test réel à {rate_test} Hz...")
    print(f"Enregistrement de {RECORD_SECONDS} secondes... Parlez !")
    try:
        stream_in = p.open(format=FORMAT, channels=CHANNELS, rate=rate_test, 
                           input=True, input_device_index=input_idx, frames_per_buffer=CHUNK)
        frames = []
        for _ in range(0, int(rate_test / CHUNK * RECORD_SECONDS)):
            frames.append(stream_in.read(CHUNK, exception_on_overflow=False))
        stream_in.stop_stream()
        stream_in.close()

        print("🎧 Lecture dans le casque...")
        stream_out = p.open(format=FORMAT, channels=CHANNELS, rate=rate_test, 
                            output=True, output_device_index=output_idx, frames_per_buffer=CHUNK)
        for data in frames:
            stream_out.write(data)
        stream_out.stop_stream()
        stream_out.close()
        return True
    except Exception as e:
        print(f"❌ Erreur durant le test : {e}")
        return False

# ==============================================================================
# LOGIQUE PRINCIPALE
# ==============================================================================
print("="*50)
print("🛠️ CALIBRAGE AUDIO INTERACTIF - PROJET NATACHA")
print("="*50)

# 1. On récupère et on liste
valid_ins, valid_outs = obtenir_peripheriques_valides()
lister_peripheriques(valid_ins, valid_outs)

try:
    # 2. Saisie sécurisée des Index
    in_idx = saisir_index_valide(valid_ins, "\n👉 Index MICROPHONE : ")
    out_idx = saisir_index_valide(valid_outs, "👉 Index CASQUE : ")
    
    # 3. Scan automatique
    freq_ok = scanner_frequences(in_idx, out_idx)
    
    if not freq_ok:
        print("\nERREUR : Aucune fréquence standard acceptée par ce matériel.")
    else:
        print("\n--- FRÉQUENCES SUPPORTÉES ---")
        for i, f in enumerate(freq_ok):
            print(f"{i+1}. {f} Hz")
        
        # Saisie sécurisée de la fréquence
        choix_f = 0
        while choix_f < 1 or choix_f > len(freq_ok):
            try:
                choix_f = int(input(f"👉 Sélectionnez une fréquence (1-{len(freq_ok)}) : "))
            except ValueError:
                pass
        
        selected_rate = freq_ok[choix_f - 1]
        
        # 4. Test auditif et sauvegarde
        if test_echo(in_idx, out_idx, selected_rate):
            if input("\nAvez-vous entendu votre voix correctement ? (o/n) : ").lower() == 'o':
                nom_in = p.get_device_info_by_index(in_idx).get('name')
                nom_out = p.get_device_info_by_index(out_idx).get('name')
                
                print(f"\n💾 Mise à jour du fichier .env...")
                with open(".env", "w") as env_file:
                    env_file.write(f"MIC_DEVICE_NAME={nom_in}\n")
                    env_file.write(f"SPEAKER_DEVICE_NAME={nom_out}\n")
                    env_file.write(f"AUDIO_SAMPLE_RATE={selected_rate}\n")
                
                print("✅ Configuration sauvegardée !")
            else:
                print("\n🔄 Calibrage annulé.")
        else:
            print("\n❌ Échec du test d'écho.")

except KeyboardInterrupt:
    print("\n\nArrêt du script.")
finally:
    p.terminate()
