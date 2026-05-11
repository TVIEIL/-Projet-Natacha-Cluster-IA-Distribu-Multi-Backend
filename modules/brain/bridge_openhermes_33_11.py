# ==============================================================================
# PROJET : NATACHA - Assistant IA Distribué & Autonome
# VERSION : 33.11 (Résilience llama-server)
# AUTEUR : Thierry VIEIL
# DATE : 03 Mai 2026
# ENVIRONNEMENT : Ubuntu / Python 3 (Cerveau Central)
# MATÉRIEL : i5-14500 
# ==============================================================================
#
# DESCRIPTION :
# Ce script (bridge) constitue le noyau cognitif de Natacha. Il orchestre :
# 1. MÉMOIRE RELATIONNELLE : Accès aux souvenirs personnels de Thierry via ChromaDB.
# 2. EXPERTISE 2026 : Consultation des actualités et news indexées localement.
# 3. SAVOIR DÉTERMINISTE (NOUVEAU) : Interrogation du serveur Kiwix local 
#    (192.168.1.100) pour extraire des connaissances fiables (Wikipedia Physique).
#
# PHILOSOPHIE v33.11 :
# - suppression libération de slots llama-server
#
# DÉPENDANCES :
# - chroma_db, requests, beautifulsoup4 (bs4), paho-mqtt
# - socket, queue, ThreadPoolExecutor
# ==============================================================================

import json, time, requests, chromadb, threading, re, locale
from datetime import datetime
from chromadb.utils import embedding_functions
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import requests
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
                    # NORMALISATION : On ignore la date avant de comparer
                    contenu_pur = donnee.split(":", 1)[1].strip() if ":" in donnee else donnee.strip()
                    
                    # Vérification dans la base Expertise
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
            # Test de socket rapide (timeout de 2 secondes)
            with socket.create_connection((ip, port), timeout=2):
                rapport[service] = "✅ OK"
        except (socket.timeout, ConnectionRefusedError):
            rapport[service] = "❌ HORS LIGNE"

    return rapport



def extraire_connaissance_wiki(sujet):
    """Interroge la base de physique locale et nettoie le HTML."""
    url = f"{KIWIX_URL}/search?pattern={sujet}"
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # On récupère les paragraphes pour éviter les balises HTML
            paragraphes = soup.find_all('p')
            if paragraphes:
                # On prend les deux premiers paragraphes pour le contexte
                return " ".join([p.text for p in paragraphes[:2]])
    except Exception as e:
        print(f"⚠️ Erreur de liaison Kiwix : {e}")
    return None
        

def traiter_question(question, client):
    print("  [Step 1] Début du traitement parallélisé...")
    global KIWIX_OK
    q_low = question.lower()
    print(f"\nThierry: {question}") #
    
    now = datetime.now()
    h_str = now.strftime("%A %d %B %Y à %Hh%M")
    # Calcul basé sur la naissance le 03/12/1974
    anniv_passe = (now.month > 12) or (now.month == 12 and now.day >= 3)
    age = (now.year - 1974) if anniv_passe else (now.year - 1974 - 1)

    mots_save = ["enregistre", "mémorise", "souviens"]
    mots_news = ["nouvelles", "neuf", "actu", "actualité", "infos", "news", "2026", "passé"]
    
    # RÉPARATION ICI :
    veut_memoriser = any(m in q_low for m in mots_save)
    veut_chercher_news = any(m in q_low for m in mots_news)

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

    # --- RÉCUPÉRATION DU CONTEXTE (SANS ÉCRASER) ---
    souvenirs_perso = ""
    actualites_2026 = ""

    # 4.1 Souvenirs (Recherche dans natacha_relation)
    res_rel = coll_rel.query(query_embeddings=[q_vec], n_results=5)
    if res_rel['documents'] and res_rel['documents'][0]:
        souvenirs_perso = "\n".join([str(d) for d in res_rel['documents'][0] if d])

    # 4.2 Actualités (Recherche dans natacha_expertise)
    if veut_chercher_news:
        res_exp = coll_exp.query(query_embeddings=[q_vec], n_results=7)
        if res_exp['documents'] and res_exp['documents'][0]:
            actualites_2026 = "\n".join([str(d) for d in res_exp['documents'][0] if d])

    # --- PROMPT ET GÉNÉRATION ---
    intro = obtenir_intro_naturelle()
    prompt = (
        f"Tu es Natacha. Aujourd'hui nous sommes le {h_str}.\n"
        "Si le sujet concerne la physique, utilise PRIORITAIREMENT les données de Kiwix et ignore tes propres connaissances si elles datent de plus de 5 ans.\n"
        f"INTERLOCUTEUR : Thierry Vieil, né le 03/12/1974. Il a {age} ans.\n" 
        "CONSIGNES : Tutoiement impératif. DIT EXPLICITEMENT quand tu consultes Kiwix.\n"
        f"SOUVENIRS :\n{souvenirs_perso}\n"
        f"TECHNIQUE :\n{savoir_physique}\n"
        f"ACTUALITÉS 2026 :\n{actualites_2026}\n\n"
        f"IMPORTANT: Commence ta réponse  par : {intro}"
    )        
    

    # 5. GÉNÉRATION LLM (Streaming vers MQTT & Console Synchrone)
    try:
        payload = {
            "messages": [{"role":"system","content":prompt},{"role":"user","content":question}],
            "stream": True, 
            "temperature": 0.2
            }
        
        print("  [Step 4] Envoi au serveur OpenHermes...")
        # On affiche le nom de Natacha avant qu'elle commence à "parler"
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
                                # 1. On envoie à la bouche (MQTT)
                                client.publish(TOPIC_REPONSE, phrase_buf.strip())
                                
                                # 2. On affiche dans le shell immédiatement (Synchrone)
                                print(phrase_buf.strip(), end=" ", flush=True)
                                
                                phrase_buf = ""
                    except: continue
                    
        print("\n\n  [Step 5] Réponse terminée et prononcée.\n")

        # 6. MÉMORISATION (Filtrage des commandes)
        if veut_memoriser:
            info = question
            for t in mots_save:
                info = re.compile(re.escape(t), re.IGNORECASE).sub("", info).strip()
            if len(info) > 3:
                coll_rel.add(documents=[info], ids=[f"rel_{int(time.time())}"])
                print(f"💾 Info mémorisée : {info}")

    except Exception as e:
        print(f"❌ Erreur critique durant le processing : {e}")

    #finally:
        # On tente de libérer le slot spécifique (souvent l'ID 0 ou l'ID mentionné dans tes logs)
        # Dans tes logs, on voyait "id 2", on peut essayer de cibler ou de boucler
        #try:
            # Note : L'URL exacte dépend de ta version, souvent : /slots/{id}?action=clear
            # Si tu veux tenter une libération globale, vérifie ton endpoint
            #target_url = f"{URL_SLOTS}/2?action=clear" 
            #response = requests.post(target_url, timeout=3)
        
            #if response.status_code == 200:
                #print("✅ Slot 2 libéré (Mémoire rafraîchie).")
            #elif response.status_code == 501:
                #print("⚠️ Le serveur ne supporte pas cette méthode de libération directe.")
        #except Exception as e:
            #print(f"❌ Échec de communication avec le cerveau : {e}")
            
            
# --- MQTT ---
def on_message(client, userdata, msg):
    p = msg.payload.decode()
    
    # On définit le type d'action pour le worker
    action = None
    if msg.topic == TOPIC_QUESTION:
        action = ("QUESTION", p)
    elif msg.topic == TOPIC_APPRENDRE:
        action = ("APPRENDRE", p)
    elif msg.topic == TOPIC_RAZ and p == "CONFIRM_RAZ":
        action = ("RAZ", None)

    if action:
        try:
            # On tente d'ajouter l'action à la file sans bloquer
            file_questions.put(action, block=False)
        except queue.Full:
            print(f"⚠️ Système saturé, action {action[0]} ignorée.")
            
 

# Utilisation au démarrage de Natacha
status = verifier_sante_systeme()
KIWIX_OK = (status.get("Kiwix (Savoir)") == "✅ OK") # Variable globale pour la suite

for service, etat in status.items():
    print(f"[{etat}] {service}")
    

if "❌ HORS LIGNE" in status.values():
    print("\n⚠️ ALERTE : Natacha risque de fonctionner en mode dégradé (hallucinations possibles).")

KIWIX_OK = (status.get("Kiwix (Savoir)") == "✅ OK") # Variable globale pour la suite

if not KIWIX_OK:
    print("\n⚠️ ALERTE : KIWIX Ko! Natacha en mode dégradé.")

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(BROKER, 1883)
client.subscribe([(TOPIC_QUESTION, 0), (TOPIC_APPRENDRE, 0), (TOPIC_RAZ, 0)])

#  On lance ce "travailleur" une seule fois au démarrage
threading.Thread(target=worker_natacha, daemon=True).start()

print(f"🚀 Natacha v33.11 en ligne. (Résilience llama-server)")
client.loop_forever()
