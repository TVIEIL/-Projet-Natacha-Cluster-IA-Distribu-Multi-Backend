# ==============================================================================
# PROJET : NATACHA - Assistant IA Distribué & Autonome
# VERSION : 33.12 (Résilience llama-server & Voyage Temporel Actualités)
# AUTEUR : Thierry VIEIL
# DATE : 03 Mai 2026
# ENVIRONNEMENT : Ubuntu / Python 3 (Cerveau Central)
# MATÉRIEL : i5-14500 
# ==============================================================================

import json, time, requests, chromadb, threading, re, locale
import os  
from datetime import datetime
from chromadb.utils import embedding_functions
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from bs4 import BeautifulSoup
import socket
import queue
from concurrent.futures import ThreadPoolExecutor
import random
from dotenv import load_dotenv, set_key

# ==============================================================================
# 1. GESTION DYNAMIQUE DE LA CONFIGURATION (.env)
# ==============================================================================
def charger_ou_creer_env():
    env_path = ".env"
    if not os.path.exists(env_path):
        print("📁 Création du fichier .env avec les valeurs par défaut...")
        with open(env_path, "w") as f:
            f.write("# CONFIGURATION NATACHA - CERVEAU\n")
            f.write("BROKER_IP=127.0.0.1\n")
            f.write("LLAMA_SERVER_URL=http://127.0.0.1:8000/v1/chat/completions\n")
            f.write("KIWIX_URL=http://192.168.1.100:8080\n")
            f.write("CHROMA_PATH=./memoire_chroma\n")
        print("✅ Fichier .env créé. Adaptez les IPs si nécessaire.")
    
    load_dotenv(env_path)

# Chargement impératif avant l'initialisation des variables globales
charger_ou_creer_env()

# --- CONFIGURATION (Pilotée par le .env) ---
BROKER = os.getenv("BROKER_IP", "127.0.0.1")
URL_SERVEUR = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:8000/v1/chat/completions")
KIWIX_URL = os.getenv("KIWIX_URL", "http://192.168.1.100:8080")
CHROMA_DIR = os.getenv("CHROMA_PATH", "./memoire_chroma")
URL_SLOTS = URL_SERVEUR.replace("/v1/chat/completions", "/slots/0?action=release")

TOPIC_QUESTION, TOPIC_REPONSE = "natacha/question", "natacha/reponse"
TOPIC_APPRENDRE, TOPIC_RAZ = "natacha/apprendre", "natacha/raz_memoire"

# File d'attente pour les questions
file_questions = queue.Queue(maxsize=1)

# ==============================================================================
# 2. INITIALISATION DES COMPOSANTS
# ==============================================================================
try: 
    locale.setlocale(locale.LC_TIME, "fr_FR.utf8")
except: 
    pass

verrou_natacha = threading.Lock()
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
emb_fn = embedding_functions.DefaultEmbeddingFunction()
coll_rel = chroma_client.get_or_create_collection(name="natacha_relation", embedding_function=emb_fn)
coll_exp = chroma_client.get_or_create_collection(name="natacha_expertise", embedding_function=emb_fn)

# ==============================================================================
# 3. FONCTIONS OUTILS ET DIAGNOSTIC
# ==============================================================================
def obtenir_intro_naturelle():
    tournures = [
        "Alors Thierry, concernant ta question :",
        "Écoute Thierry, j'ai regardé ça pour toi :",
        "C'est une question intéressante ! Voilà ce que je sais :",
        "D'après mes informations, Thierry :",
        "Pour répondre à ta demande :",
        "Alors, sur ce point précis :",
        "Tiens, voici ce que j'ai trouvé :",
        "" 
    ]
    return random.choice(tournures)

def verifier_sante_systeme():
    config = {
        "Kiwix (Savoir)": (KIWIX_URL.split("//")[1].split(":")[0], int(KIWIX_URL.split(":")[-1])),
        "MQTT (Reseau)": (BROKER, 1883),
    }
    rapport = {}
    print("🔍 DIAGNOSTIC SYSTÈME EN COURS...")
    for service, (ip, port) in config.items():
        try:
            with socket.create_connection((ip, port), timeout=2):
                rapport[service] = "✅ OK"
        except:
            rapport[service] = "❌ HORS LIGNE"
    return rapport

def extraire_connaissance_wiki(sujet):
    url = f"{KIWIX_URL}/search?pattern={sujet}"
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            paragraphes = soup.find_all('p')
            if paragraphes:
                return " ".join([p.text for p in paragraphes[:2]])
    except Exception as e:
        print(f"⚠️ Erreur de liaison Kiwix : {e}")
    return None

# ==============================================================================
# 4. LOGIQUE MÉTIER ET TRAITEMENT
# ==============================================================================
def traiter_question(question, client_mqtt):
    print("  [Step 1] Début du traitement parallélisé...")
    global KIWIX_OK
    q_low = question.lower()
    print(f"\nThierry: {question}")
    
    now = datetime.now()
    h_str = now.strftime("%A %d %B %Y à %Hh%M")
    
    annee_cible = str(now.year)
    match_annee = re.search(r'\b(20[0-9]{2})\b', q_low)
    if match_annee:
        annee_cible = match_annee.group(1)

    anniv_passe = (now.month > 12) or (now.month == 12 and now.day >= 3)
    age = (now.year - 1974) if anniv_passe else (now.year - 1974 - 1)

    mots_save = ["enregistre", "mémorise", "souviens"]
    mots_news = ["nouvelles", "neuf", "actu", "actualité", "infos", "news", "2026", "passé"]
    
    veut_memoriser = any(m in q_low for m in mots_save)
    veut_chercher_news = any(m in q_low for m in mots_news) or match_annee is not None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futur_souvenirs = executor.submit(emb_fn, [question])
        futur_wiki = None
        mots_cles_techniques = ["physique", "tension", "kiwix", "wiki", "recherche", "zim"]
        if KIWIX_OK and any(mot in q_low for mot in mots_cles_techniques):
            print("  [Step 3] Lancement Kiwix parallèle...")
            futur_wiki = executor.submit(extraire_connaissance_wiki, question)

        try:
            q_vec = futur_souvenirs.result(timeout=10)[0]
            savoir_physique = futur_wiki.result(timeout=10) if futur_wiki else ""
        except Exception as e:
            print(f"⚠️ Synchro KO : {e}")
            savoir_physique = ""

    souvenirs_perso = ""
    contexte_actualites = ""

    res_rel = coll_rel.query(query_embeddings=[q_vec], n_results=5)
    if res_rel['documents'] and res_rel['documents'][0]:
        souvenirs_perso = "\n".join([str(d) for d in res_rel['documents'][0] if d])

    if veut_chercher_news:
        res_exp = coll_exp.query(query_embeddings=[q_vec], n_results=20)
        actualites_filtrees = []
        if res_exp['documents'] and res_exp['documents'][0]:
            for doc in res_exp['documents'][0]:
                if doc and f"ACTU {annee_cible}" in str(doc):
                    actualites_filtrees.append(str(doc))
                if len(actualites_filtrees) >= 7: break
        contexte_actualites = "\n".join(actualites_filtrees)

    intro = obtenir_intro_naturelle()
    prompt = (
        f"Tu es Natacha. Aujourd'hui nous sommes le {h_str}.\n"
        "Si le sujet concerne la physique, utilise PRIORITAIREMENT les données de Kiwix.\n"
        f"INTERLOCUTEUR : Thierry Vieil, né le 03/12/1974. Il a {age} ans.\n" 
        "CONSIGNES : Tutoiement impératif. DIT EXPLICITEMENT quand tu consultes Kiwix.\n"
        f"SOUVENIRS :\n{souvenirs_perso}\n"
        f"TECHNIQUE :\n{savoir_physique}\n"
        f"ACTUALITÉS {annee_cible} :\n{contexte_actualites}\n\n"
        f"IMPORTANT: Commence ta réponse par : {intro}"
    )        
    
    try:
        payload = {"messages": [{"role":"system","content":prompt},{"role":"user","content":question}], "stream": True, "temperature": 0.2}
        print("\nNa: ", end="", flush=True) 
        with requests.post(URL_SERVEUR, json=payload, stream=True) as r:
            reponse_full, phrase_buf = "", ""
            for line in r.iter_lines():
                if line:
                    line_str = line.decode('utf-8').replace("data: ", "").strip()
                    if line_str == "[DONE]": break
                    try:
                        token = json.loads(line_str)['choices'][0]['delta'].get('content', '')
                        if token:
                            reponse_full += token
                            phrase_buf += token
                            if any(p in token for p in [".", "!", "?", "\n"]):
                                client_mqtt.publish(TOPIC_REPONSE, phrase_buf.strip())
                                print(phrase_buf.strip(), end=" ", flush=True)
                                phrase_buf = ""
                    except: continue
        print("\n\n  [Step 5] Réponse terminée.\n")

        if veut_memoriser:
            info = question
            for t in mots_save: info = re.compile(re.escape(t), re.IGNORECASE).sub("", info).strip()
            if len(info) > 3:
                coll_rel.add(documents=[info], ids=[f"rel_{int(time.time())}"])
                print(f"💾 Info mémorisée : {info}")
    except Exception as e:
        print(f"❌ Erreur critique : {e}")

# ==============================================================================
# 5. WORKER ET MQTT
# ==============================================================================
def worker_natacha():
    while True:
        try:
            type_action, donnee = file_questions.get()
            with verrou_natacha:
                if type_action == "QUESTION": traiter_question(donnee, client)
                elif type_action == "APPRENDRE":
                    contenu_pur = donnee.split(":", 1)[1].strip() if ":" in donnee else donnee.strip()
                    if not coll_exp.get(where_document={"$contains": contenu_pur})['ids']:
                        coll_exp.add(documents=[donnee], ids=[f"exp_{int(time.time())}"])
                        print(f"📝 Appris : {contenu_pur[:50]}...")
                elif type_action == "RAZ":
                    coll_rel.delete(where={})
                    coll_exp.delete(where={})
                    print("Sweep : Mémoire réinitialisée.")
        except Exception as e: print(f"❌ Erreur Worker : {e}")
        finally: file_questions.task_done()

def on_message(client, userdata, msg):
    p = msg.payload.decode()
    action = None
    if msg.topic == TOPIC_QUESTION: action = ("QUESTION", p)
    elif msg.topic == TOPIC_APPRENDRE: action = ("APPRENDRE", p)
    elif msg.topic == TOPIC_RAZ and p == "CONFIRM_RAZ": action = ("RAZ", None)
    if action:
        try: file_questions.put(action, block=False)
        except queue.Full: print("⚠️ Système saturé.")

# ==============================================================================
# 6. LANCEMENT
# ==============================================================================
status = verifier_sante_systeme()
KIWIX_OK = (status.get("Kiwix (Savoir)") == "✅ OK")

for service, etat in status.items(): print(f"[{etat}] {service}")

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_message = on_message

try:
    client.connect(BROKER, 1883)
    client.subscribe([(TOPIC_QUESTION, 0), (TOPIC_APPRENDRE, 0), (TOPIC_RAZ, 0)])
except Exception as e:
    print(f"❌ Connexion Broker Impossible ({BROKER}) : {e}")
    exit(1)

threading.Thread(target=worker_natacha, daemon=True).start()
print(f"🚀 Natacha v33.12 en ligne. (DB: {CHROMA_DIR})")
client.loop_forever()
