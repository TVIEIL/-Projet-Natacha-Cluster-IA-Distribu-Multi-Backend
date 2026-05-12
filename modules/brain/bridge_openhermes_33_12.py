# ==============================================================================
# PROJET : NATACHA - Assistant IA Distribué & Autonome
# VERSION : 33.12 (Résilience llama-server & Voyage Temporel Actualités)
# AUTEUR : Thierry VIEIL
# DATE : 03 Mai 2026
# ENVIRONNEMENT : Ubuntu / Python 3 (Cerveau Central)
# MATÉRIEL : i5-14500 
# ==============================================================================
#
# DESCRIPTION :
# Ce script (bridge) constitue le noyau cognitif de Natacha. Il orchestre :
# 1. MÉMOIRE RELATIONNELLE : Accès aux souvenirs personnels de Thierry via ChromaDB.
# 2. EXPERTISE DYNAMIQUE : Consultation des actualités filtrées par année.
# 3. SAVOIR DÉTERMINISTE : Interrogation du serveur Kiwix local.
# ==============================================================================

import json, time, requests, chromadb, threading, re, locale
from datetime import datetime
from chromadb.utils import embedding_functions
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from bs4 import BeautifulSoup
import socket
import queue
from concurrent.futures import ThreadPoolExecutor
import random

# --- CONFIGURATION ---
BROKER = "127.0.0.1"
URL_SERVEUR = "http://127.0.0.1:8000/v1/chat/completions"
URL_SLOTS = "http://127.0.0.1:8000/slots/0?action=release"
TOPIC_QUESTION, TOPIC_REPONSE = "natacha/question", "natacha/reponse"
TOPIC_APPRENDRE, TOPIC_RAZ = "natacha/apprendre", "natacha/raz_memoire"
KIWIX_URL = "http://192.168.1.100:8080"

#  On crée une file d'attente pour les questions d'une seule place
file_questions = queue.Queue(maxsize=1)

# --- INITIALISATION ---
try: locale.setlocale(locale.LC_TIME, "fr_FR.utf8")
except: pass

verrou_natacha = threading.Lock()
chroma_client = chromadb.PersistentClient(path="./memoire_chroma")
emb_fn = embedding_functions.DefaultEmbeddingFunction()
coll_rel = chroma_client.get_or_create_collection(name="natacha_relation", embedding_function=emb_fn)
coll_exp = chroma_client.get_or_create_collection(name="natacha_expertise", embedding_function=emb_fn)

def obtenir_intro_naturelle():
    tournures = [
        "Alors Thierry, concernant ta question :",
        "Écoute Thierry, j'ai regardé ça pour toi :",
        "C'est une question intéressante ! Voilà ce que je sais :",
        "D'après mes informations, Thierry :",
        "Pour répondre à ta demande :",
        "Alors, sur ce point précis :",
        "Tiens, voici ce que j'ai trouvé :",
        "" # Parfois, commencer directement est encore plus naturel
    ]
    return random.choice(tournures)

def worker_natacha():
    while True:
        try:
            type_action, donnee = file_questions.get()
            print(f"⚙️ Worker : Action reçue -> {type_action}")
        
            with verrou_natacha:
                if type_action == "QUESTION":
                    traiter_question(donnee, client)
            
                elif type_action == "APPRENDRE":
                    contenu_pur = donnee.split(":", 1)[1].strip() if ":" in donnee else donnee.strip()
                    deja_connu = coll_exp.get(where_document={"$contains": contenu_pur})
                    
                    if not deja_connu['ids']:
                        print(f"📝 Nouvelle info détectée : {contenu_pur[:50]}...")
                        coll_exp.add(documents=[donnee], ids=[f"exp_{int(time.time())}"])
                    else:
                        print(f"🚫 Doublon ignoré : {contenu_pur[:50]}...")
            
                elif type_action == "RAZ":
                    print("Sweep : Réinitialisation de la mémoire...")
                    coll_rel.delete(where={})
                    coll_exp.delete(where={})
                        
        except Exception as e:
            print(f"❌ Erreur critique dans le Worker : {e}")
        finally:
            file_questions.task_done()

def verifier_sante_systeme():
    config = {
        "Kiwix (Savoir)": ("192.168.1.100", 8080),
        "MQTT (Reseau)": ("127.0.0.1", 1883),  # Ou l'IP de ton broker
    }
    
    rapport = {}
    print("🔍 DIAGNOSTIC SYSTÈME EN COURS...")

    for service, (ip, port) in config.items():
        try:
            with socket.create_connection((ip, port), timeout=2):
                rapport[service] = "✅ OK"
        except (socket.timeout, ConnectionRefusedError):
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
        
def traiter_question(question, client):
    print("  [Step 1] Début du traitement parallélisé...")
    global KIWIX_OK
    q_low = question.lower()
    print(f"\nThierry: {question}")
    
    now = datetime.now()
    h_str = now.strftime("%A %d %B %Y à %Hh%M")
    
    # Détection de l'année ciblée pour la recherche d'actualités
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

    # --- EXÉCUTION PARALLÈLE ---
    with ThreadPoolExecutor(max_workers=2) as executor:
        futur_souvenirs = executor.submit(emb_fn, [question])
        futur_wiki = None
        
        mots_cles_techniques = ["physique", "tension", "kiwix", "wiki", "recherche", "zim"]
        if KIWIX_OK and any(mot in q_low for mot in mots_cles_techniques):
            print("  [Step 3] Lancement Kiwix parallèle...")
            futur_wiki = executor.submit(extraire_connaissance_wiki, question)

        try:
            q_vec = futur_souvenirs.result(timeout=10)[0]
            print("  [Step 2] Embedding OK")
            savoir_physique = futur_wiki.result(timeout=10) if futur_wiki else ""
        except Exception as e:
            print(f"⚠️ Synchro KO : {e}")
            savoir_physique = ""

    # --- RÉCUPÉRATION DU CONTEXTE ---
    souvenirs_perso = ""
    contexte_actualites = ""

    # 4.1 Souvenirs (Recherche dans natacha_relation)
    res_rel = coll_rel.query(query_embeddings=[q_vec], n_results=5)
    if res_rel['documents'] and res_rel['documents'][0]:
        souvenirs_perso = "\n".join([str(d) for d in res_rel['documents'][0] if d])

    # 4.2 Actualités (Recherche dans natacha_expertise avec POST-FILTRAGE TEMPOREL)
    if veut_chercher_news:
        # On demande 20 résultats au lieu de 7 pour avoir du choix avant filtrage
        res_exp = coll_exp.query(query_embeddings=[q_vec], n_results=20)
        actualites_filtrees = []
        
        if res_exp['documents'] and res_exp['documents'][0]:
            for doc in res_exp['documents'][0]:
                if doc:
                    balise_recherche = f"ACTU {annee_cible}"
                    if balise_recherche in str(doc):
                        actualites_filtrees.append(str(doc))
                    if len(actualites_filtrees) >= 7:
                        break # On s'arrête quand on a nos 7 actus valides
                        
        contexte_actualites = "\n".join(actualites_filtrees)
        print(f"  [Step 4.2] {len(actualites_filtrees)} actualités filtrées pour l'année {annee_cible}")

    # --- PROMPT ET GÉNÉRATION ---
    intro = obtenir_intro_naturelle()
    prompt = (
        f"Tu es Natacha. Aujourd'hui nous sommes le {h_str}.\n"
        "Si le sujet concerne la physique, utilise PRIORITAIREMENT les données de Kiwix et ignore tes propres connaissances si elles datent de plus de 5 ans.\n"
        f"INTERLOCUTEUR : Thierry Vieil, né le 03/12/1974. Il a {age} ans.\n" 
        "CONSIGNES : Tutoiement impératif. DIT EXPLICITEMENT quand tu consultes Kiwix.\n"
        f"SOUVENIRS :\n{souvenirs_perso}\n"
        f"TECHNIQUE :\n{savoir_physique}\n"
        f"ACTUALITÉS {annee_cible} :\n{contexte_actualites}\n\n"
        f"IMPORTANT: Commence ta réponse par : {intro}"
    )        
    
    # 5. GÉNÉRATION LLM (Streaming vers MQTT & Console Synchrone)
    try:
        payload = {
            "messages": [{"role":"system","content":prompt},{"role":"user","content":question}],
            "stream": True, 
            "temperature": 0.2
            }
        
        print("  [Step 4] Envoi au serveur OpenHermes...")
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
                            
                            # SYNCHRONISATION : Dès qu'une phrase est terminée
                            if any(p in token for p in [".", "!", "?", "\n"]):
                                client.publish(TOPIC_REPONSE, phrase_buf.strip())
                                print(phrase_buf.strip(), end=" ", flush=True)
                                phrase_buf = ""
                    except: continue
                    
        print("\n\n  [Step 5] Réponse terminée et prononcée.\n")

        # 6. MÉMORISATION
        if veut_memoriser:
            info = question
            for t in mots_save:
                info = re.compile(re.escape(t), re.IGNORECASE).sub("", info).strip()
            if len(info) > 3:
                coll_rel.add(documents=[info], ids=[f"rel_{int(time.time())}"])
                print(f"💾 Info mémorisée : {info}")

    except Exception as e:
        print(f"❌ Erreur critique durant le processing : {e}")

# --- MQTT ---
def on_message(client, userdata, msg):
    p = msg.payload.decode()
    
    action = None
    if msg.topic == TOPIC_QUESTION:
        action = ("QUESTION", p)
    elif msg.topic == TOPIC_APPRENDRE:
        action = ("APPRENDRE", p)
    elif msg.topic == TOPIC_RAZ and p == "CONFIRM_RAZ":
        action = ("RAZ", None)

    if action:
        try:
            file_questions.put(action, block=False)
        except queue.Full:
            print(f"⚠️ Système saturé, action {action[0]} ignorée.")
            
# Utilisation au démarrage de Natacha
status = verifier_sante_systeme()
KIWIX_OK = (status.get("Kiwix (Savoir)") == "✅ OK")

for service, etat in status.items():
    print(f"[{etat}] {service}")
    
if "❌ HORS LIGNE" in status.values():
    print("\n⚠️ ALERTE : Natacha risque de fonctionner en mode dégradé.")

KIWIX_OK = (status.get("Kiwix (Savoir)") == "✅ OK")

if not KIWIX_OK:
    print("\n⚠️ ALERTE : KIWIX Ko! Natacha en mode dégradé.")

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(BROKER, 1883)
client.subscribe([(TOPIC_QUESTION, 0), (TOPIC_APPRENDRE, 0), (TOPIC_RAZ, 0)])

threading.Thread(target=worker_natacha, daemon=True).start()

print(f"🚀 Natacha v33.12 en ligne. (Filtrage Temporel ChromaDB)")
client.loop_forever()
