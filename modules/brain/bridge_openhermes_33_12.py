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
# PROJET NATACHA - MODULE CERVEAU NATACHA
# ==============================================================================

# ==============================================================================
# PROJET : NATACHA - Assistant IA Distribué & Autonome
# VERSION : 33.12 (Résilience llama-server & Voyage Temporel Actualités)
# AUTEUR : Thierry VIEIL
# DATE : 30 Mai 2026
# ENVIRONNEMENT : Ubuntu / Python 3 (Cerveau Central)
# MATÉRIEL : i5-14500 
# ==============================================================================
# PROJET NATACHA - MODULE CERVEAU NATACHA v33.12au_fusion
# ==============================================================================

import json, time, requests, chromadb, threading, re, locale, socket, queue, random, os, html, urllib.parse
from datetime import datetime
from chromadb.utils import embedding_functions
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dotenv import load_dotenv

# --- CONFIGURATION DU MODULE ŒIL ---
OEIL_ACTIF = True # <-- PASSE A FALSE POUR DÉSACTIVER L'ŒIL

# 1. On définit ton identifiant "Secret"
INDICATIF_MAITRE = "F4HRB"

def verifier_identite(texte_a_verifier):
    signal_propre = texte_a_verifier.upper().replace(" ", "").replace("-", "")
    return "F4HRB" in signal_propre

# ==============================================================================
# 1. GESTION CONFIGURATION
# ==============================================================================
def charger_ou_creer_env(chemin_complet):
    if not os.path.exists(chemin_complet):
        with open(chemin_complet, "w") as f:
            f.write("BROKER_IP=127.0.0.1\nLLAMA_SERVER_URL=http://127.0.0.1:8000/v1/chat/completions\nKIWIX_URL=http://192.168.1.100:8080\nCHROMA_PATH=./memoire_chroma\n")

base_path = Path(__file__).resolve().parent
env_path = base_path / ".env"
charger_ou_creer_env(env_path)
load_dotenv(dotenv_path=env_path)

BROKER = os.getenv("BROKER_IP", "127.0.0.1")
URL_SERVEUR = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:8000/v1/chat/completions")
KIWIX_URL = os.getenv("KIWIX_URL", "http://192.168.1.100:8080")
CHROMA_DIR = os.getenv("CHROMA_PATH", "./memoire_chroma")

TOPIC_QUESTION, TOPIC_REPONSE = "natacha/question", "natacha/reponse"
TOPIC_APPRENDRE, TOPIC_RAZ = "natacha/apprendre", "natacha/raz_memoire"
TOPIC_OEIL_DETECTION = "natacha/oeil_detection"

oeil_statut, oeil_veste, oeil_emotion = "absent", "Inconnue", "Neutre"
en_traitement, buffer_oeil = False, None
file_questions = queue.Queue(maxsize=10)

# ==============================================================================
# 2. INITIALISATION ET SANTÉ
# ==============================================================================
def verifier_sante_systeme():
    config = {
        "Kiwix (Savoir)": (KIWIX_URL.split("//")[1].split(":")[0], int(KIWIX_URL.split(":")[-1])),
        "MQTT (Reseau)": (BROKER, 1883),
    }
    rapport = {}
    print("🔍 DIAGNOSTIC SYSTÈME EN COURS...")
    for service, (ip, port) in config.items():
        succes = False
        for essai in range(3):
            try:
                with socket.create_connection((ip, port), timeout=2):
                    rapport[service] = "OK ✅ "
                    succes = True
                    break
            except:
                if essai < 2: time.sleep(5)
        if not succes: rapport[service] = "HORS LIGNE ❌ "
    return rapport

# Initialisation ChromaDB
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
emb_fn = embedding_functions.DefaultEmbeddingFunction()
coll_rel = chroma_client.get_or_create_collection(name="natacha_relation", embedding_function=emb_fn)
coll_exp = chroma_client.get_or_create_collection(name="natacha_expertise", embedding_function=emb_fn)

# ==============================================================================
# 3. LOGIQUE MÉTIER ET TRAITEMENT
# ==============================================================================
def traiter_question(question, client_mqtt):
    global en_traitement, oeil_statut, oeil_veste, oeil_emotion, buffer_oeil
    en_traitement = True
    
    # ... (le reste de ton code traiter_question reste identique)
    # [Note: Dans ton bloc contexte_oeil, n'oublie pas de vérifier OEIL_ACTIF]
    
    if OEIL_ACTIF and oeil_statut == "present":
        contexte_oeil = f"Thierry est devant son établi, il porte un vêtement {oeil_veste} et semble {oeil_emotion}."
    else:
        contexte_oeil = "Thierry est absent de son établi."
    
    # ... (fin de la fonction traitée normalement)
    en_traitement = False

def on_message(client, userdata, msg):
    global oeil_statut, oeil_veste, oeil_emotion, en_traitement, buffer_oeil
    if msg.topic == TOPIC_OEIL_DETECTION and OEIL_ACTIF:
        try:
            d = json.loads(msg.payload.decode())
            if en_traitement: buffer_oeil = d
            else: oeil_statut, oeil_veste, oeil_emotion = d.get("statut"), d.get("couleur_vetement"), d.get("emotion")
        except: pass
        return
    # ... (reste du on_message)

# ==============================================================================
# 6. LANCEMENT
# ==============================================================================
status = verifier_sante_systeme()
KIWIX_OK = "OK" in status.get("Kiwix (Savoir)", "")
for service, etat in status.items(): print(f"[{etat}] {service}")
if not KIWIX_OK: print("⚠️ Attention : Kiwix est détecté comme HORS LIGNE.")

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(BROKER, 1883)
client.subscribe([(TOPIC_QUESTION, 0), (TOPIC_APPRENDRE, 0), (TOPIC_RAZ, 0), (TOPIC_OEIL_DETECTION, 0)])
threading.Thread(target=worker_natacha, daemon=True).start()
print(f"🚀 Natacha en ligne (Œil: {'ON' if OEIL_ACTIF else 'OFF'}).")
client.loop_forever()
