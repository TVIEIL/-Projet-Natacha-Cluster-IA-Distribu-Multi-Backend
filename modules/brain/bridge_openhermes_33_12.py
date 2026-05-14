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
import socket
import queue
from concurrent.futures import ThreadPoolExecutor
import random
from dotenv import load_dotenv, set_key
import urllib.parse  # Utile pour nettoyer la question
import html 
from pathlib import Path



# 1. On définit ton identifiant "Secret" (tu peux le mettre dans ton .env)
INDICATIF_MAITRE = "F4HRB"

def verifier_identite(texte_a_verifier):
    # On met tout en majuscules ET on supprime tous les espaces
    signal_propre = texte_a_verifier.upper().replace(" ", "").replace("-", "")
    
    if "F4HRB" in signal_propre:
        return True
    return False

# ==============================================================================
# 1. GESTION DYNAMIQUE DE LA CONFIGURATION (.env)
# ==============================================================================
def charger_ou_creer_env(chemin_complet):
    if not os.path.exists(chemin_complet):
        print(f"📁 Création du fichier .env à : {chemin_complet}")
        with open(chemin_complet, "w") as f:
            f.write("# CONFIGURATION NATACHA - CERVEAU\n")
            f.write("BROKER_IP=127.0.0.1\n")
            f.write("LLAMA_SERVER_URL=http://127.0.0.1:8000/v1/chat/completions\n")
            f.write("KIWIX_URL=http://192.168.1.100:8080\n")
            f.write("CHROMA_PATH=./memoire_chroma\n")
        print("✅ Fichier .env créé. Adaptez les IPs si nécessaire.")
    

# 1. On trouve d'abord le chemin (On trace le circuit)
base_path = Path(__file__).resolve().parent
env_path = base_path / ".env"

# 2. On vérifie/crée le fichier (On pose le composant)
charger_ou_creer_env(env_path)
    
# 3. On charge les données dans le script (On met sous tension)
load_dotenv(dotenv_path=env_path)

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
        "Alors, concernant ta question :",
        "Écoute, j'ai regardé ça pour toi :",
        "C'est une question intéressante ! Voilà ce que je sais :",
        "D'après mes informations  :",
        "Pour répondre à ta demande :",
        "Alors, sur ce point précis :",
        "Tiens, voici ce que j'ai trouvé :",
        "Je me suis penchée sur la question, et voilà le résultat de mon analyse :",
        "Pas de souci, on fait le tour du sujet ensemble. Voilà les détails :",
        "C'est tout à fait dans mes cordes ! Laisse-moi te détailler ça :",
        "Après avoir mouliné les infos, voici ce que j'ai pu extraire :",
        "Tout de suite! Voici les points clés dont je dispose :",
        "J'ai compilé tout ça pour toi, jette un œil :",
        "C'est un excellent point ! Voilà la situation sous cet angle :",
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
                rapport[service] = "OK ✅ "
        except:
            rapport[service] = "HORS LIGNE ❌ "
    return rapport




def extraire_connaissance_wiki(question):
    global KIWIX_URL
    
    # --- CONFIGURATION DU SAVOIR ---
    # Changez le nom ici si vous utilisez une autre base Kiwix   "Livre wikipedia"
    NOM_LIVRE_KIWIX  = "wikipedia_fr_physics_maxi_2026-04"
    
    mots = [m for m in question.lower().replace("?", "").split() if len(m) > 3]
    mots_filtres = [m for m in mots if m not in ["natacha", "wiki", "cherche", "article", "lit"]]
    recherche = " ".join(mots_filtres[-2:]) if mots_filtres else question
    
    try:
        search_url = f"{KIWIX_URL}/search?content={NOM_LIVRE_KIWIX }&pattern={urllib.parse.quote(recherche)}"
        res_search = requests.get(search_url, timeout=5)
        liens = re.findall(r'href=["\'](/content/' + NOM_LIVRE_KIWIX  + r'/[^"\']+)["\']', res_search.text)
        
        if not liens: return ""

        res_article = requests.get(f"{KIWIX_URL}{liens[0]}", timeout=5)
        res_article.encoding = 'utf-8'
        
        # --- FILTRE PASSE-HAUT (Nettoyage radical) ---
        texte = html.unescape(res_article.text)
        texte = re.sub(r'<script.*?>.*?</script>', '', texte, flags=re.DOTALL) # Supprime JS
        texte = re.sub(r'<style.*?>.*?</style>', '', texte, flags=re.DOTALL)   # Supprime CSS
        texte = re.sub(r'<.*?>', ' ', texte) # Supprime HTML
        
        # Suppression des caractères spéciaux qui font bugger le tokenizer (phonétique, crochets, accolades)
        texte = re.sub(r'\[.*?\]', '', texte) # Enlève [1], [N1], etc.
        texte = re.sub(r'\{.*?\}', '', texte) # Enlève le code interne
        texte = re.sub(r'[\(\[].*?[\)\]]', '', texte) # Enlève les parenthèses de phonétique
        
        # On ne garde que les caractères "propres" (Alphanumérique + ponctuation de base)
        texte = "".join([c for c in texte if c.isalnum() or c in " .,'?!:;éàèêîôûç-"])
        
        texte_final = re.sub(r'\s+', ' ', texte).strip()
        
        # On réduit la fenêtre à 2000 chars pour ne pas saturer le contexte du i5
        return f"DONNÉES WIKI SUR {recherche.upper()} :\n{texte_final[:2000]}"

    except Exception as e:
        return ""


# ==============================================================================
# 4. LOGIQUE MÉTIER ET TRAITEMENT
# ==============================================================================

def traiter_question(question, client_mqtt):
    global KIWIX_OK
    print(f"\nInterlocuteur : {question}")
    print("  [Step 1] Début du traitement parallélisé...")
    
    # 2. Dans ta fonction de construction du prompt
    # Qui est l'interlocuteur?
    is_authenticated = verifier_identite(question)
    
    # --- 1. INITIALISATION DE TOUTES LES VARIABLES (Sécurité anti-crash) ---
    savoir_physique = ""
    souvenirs_perso = ""
    contexte_actualites = ""
    futur_wiki = None
    q_low = question.lower()
    
    # Gestion des dates et de l'âge
    now = datetime.now()
    h_str = now.strftime("%A %d %B %Y à %Hh%M")
    annee_cible = str(now.year)
    match_annee = re.search(r'\b(20[0-9]{2})\b', q_low)
    if match_annee: annee_cible = match_annee.group(1)

    anniv_passe = (now.month > 12) or (now.month == 12 and now.day >= 3)
    age = (now.year - 1974) if anniv_passe else (now.year - 1974 - 1)

    # Détection des intentions
    mots_save = ["enregistre", "mémorise", "souviens"]
    mots_news = ["nouvelles", "neuf", "actu", "actualité", "infos", "news", "2026", "passé"]
    mots_cles_wiki = ["physique", "tension", "kiwix", "wiki", "recherche", "qx", "fermi", "loi", "ohm", "ampere"]
    
    veut_memoriser = any(m in q_low for m in mots_save)
    veut_chercher_news = any(m in q_low for m in mots_news) or match_annee is not None
    veut_wiki = any(mot in q_low for mot in mots_cles_wiki)

    # --- 2. EXÉCUTION DES TÂCHES PARALLÈLES ---
    with ThreadPoolExecutor(max_workers=2) as executor:
        futur_souvenirs = executor.submit(emb_fn, [question])
        
        if KIWIX_OK and veut_wiki:
            print(f"  [Step 3] Lancement Kiwix pour : {question}")
            futur_wiki = executor.submit(extraire_connaissance_wiki, question)

        try:
            # Récupération de l'embedding pour Chroma
            q_vec = futur_souvenirs.result(timeout=10)[0]
            print("  [OK] Vecteur mémoire reçu.")

            # Récupération du savoir Kiwix si lancé
            if futur_wiki:
                savoir_physique = futur_wiki.result(timeout=15)
                if savoir_physique:
                    print(f"  [OK] Savoir Kiwix reçu ({len(savoir_physique)} chars).\n")
                    print(savoir_physique)
                else:
                    print("  [DEBUG] Kiwix n'a rien renvoyé.")
        except Exception as e:
            print(f"⚠️ Erreur lors de la synchro : {e}")
            q_vec = None # Sécurité pour la suite

    # --- 3. RÉCUPÉRATION DE LA MÉMOIRE (ChromaDB) ---
    if q_vec is not None:
        # Souvenirs personnels
        res_rel = coll_rel.query(query_embeddings=[q_vec], n_results=5)
        if res_rel['documents'] and res_rel['documents'][0]:
            souvenirs_perso = "\n".join([str(d) for d in res_rel['documents'][0] if d])

        # Actualités 2026
        if veut_chercher_news:
            res_exp = coll_exp.query(query_embeddings=[q_vec], n_results=20)
            if res_exp['documents'] and res_exp['documents'][0]:
                actualites_filtrees = [str(doc) for doc in res_exp['documents'][0] if doc and f"ACTU {annee_cible}" in str(doc)]
                contexte_actualites = "\n".join(actualites_filtrees[:7])

    # --- 4. CONSTRUCTION DU PROMPT ET ENVOI LLM ---
    # --- CONSTRUCTION DU PROMPT (v33.12w) ---
    intro = obtenir_intro_naturelle()
    
    # On s'assure que le savoir technique n'est pas "indigeste"
    contexte_wiki = savoir_physique if savoir_physique else "Aucune donnée encyclopédique trouvée."

   # --- DÉTECTION DE L'INTENTION DE DÉTAIL ---
    veut_detail = any(mot in q_low for mot in ["lit", "lis", "détaille", "explique", "wiki"])
    consigne_longueur = "Développe largement ta réponse en citant les détails du livre." if veut_detail else "Sois concise et naturelle."



    if is_authenticated:
        role_instruction = (
            "STATUT : AUTHENTIFIÉ (F4HRB). Tu parles à ton créateur Thierry VIEIL. "
            "Tutoie-le, sois complice, et accède à tous ses souvenirs sans retenue."
        )
    else:
        role_instruction = "Tu parles à un utilisateur. Reste courtoise et utilise le tutoiement."

    # --- CONSTRUCTION DU PROMPT (v33.12y - Fusion Kiwix + Chroma) ---
    prompt = (
        f"SYSTEME : Tu es Natacha, assistante IA experte. Date : {h_str}.\n\n"
        "### DONNÉES DE RÉFÉRENCE (KIWIX) :\n"
        f"{savoir_physique if savoir_physique else 'Aucune donnée encyclopédique trouvée.'}\n"
        "--------------------------\n"
        "### SOUVENIRS RÉCENTS (CHROMA) :\n"
        f"{souvenirs_perso if souvenirs_perso else 'Aucun souvenir récent trouvé.'}\n"
        "--------------------------\n\n"
        "### RÈGLES D'OR DE NATACHA :\n"
        f"{role_instruction}\n"
        "1. TU DOIS TUTOYER THIERRY. Utilise 'tu' et 'toi', jamais 'vous'.\n"
        "2. Parle de façon décontractée, comme une collègue électronicienne.\n"
        f"3. {consigne_longueur}\n"
        f"4. TA RÉPONSE COMMENCE PAR : {intro}\n"
        "RÉPONSE DE NATACHA :"
    )

    #prompt = (
    #    f"SYSTEME : Tu es Natacha, assistante IA. Date : {h_str}.\n\n"
    #    "### DONNÉES DE RÉFÉRENCE (KIWIX & MÉMOIRE) :\n"
    #    f"{contexte_wiki}\n"
    #    "--------------------------\n"
    #    f"SOUVENIRS RÉCENTS : {souvenirs_perso}\n"
    #    "--------------------------\n\n"
    #    "### CONSIGNES STRICTES :\n"
    #   "1. Tutoiement obligatoire.\n"
    #    "2. Si les données de référence sont utiles, utilise-les pour répondre.\n"
    #    f"3. TA RÉPONSE DOIT IMPÉRATIVEMENT COMMENCER PAR : {intro}\n"
    #    "4. Sois concise et naturelle.\n\n"
    #    "RÉPONSE DE NATACHA :"
    #)
    
   # prompt = (
   #   f"Tu es Natacha. Aujourd'hui nous sommes le {h_str}.\n"
   #    "Si le sujet est scientifique, utilise PRIORITAIREMENT les données de Kiwix.\n"
   #     f"INTERLOCUTEUR : Thierry Vieil, né le 03/12/1974. Il a {age} ans.\n" 
   #    "CONSIGNES : Tutoiement impératif. DIT EXPLICITEMENT quand tu consultes Kiwix.\n"
   #     f"SOUVENIRS :\n{souvenirs_perso}\n"
   #     f"SAVOIR KIWIX :\n{savoir_physique}\n"
   #     f"ACTUALITÉS {annee_cible} :\n{contexte_actualites}\n\n"
   #    f"IMPORTANT: Commence ta réponse par : {intro}"
   # )
    #prompt = (
    #    f"Tu es Natacha. Aujourd'hui nous sommes le {h_str}.\n"
    #   "Tu as accès à un livre de physique (KIWIX) ci-dessous.\n"
    #    "Si les données sont utiles, utilise-les. SINON, réponds avec tes propres connaissances.\n"
    #    f"SAVOIR KIWIX :\n{savoir_physique if savoir_physique else 'Aucune donnée trouvée dans le livre.'}\n\n"
    #    f"CONSIGNE : Tutoiement. Réponds directement à l'interlocuteur.\n"
    #    f"IMPORTANT : Commence obligatoirement par : {intro}"
    #)

    try:
        print("  [Step 4] Envoi au LLM...")
        payload = {"messages": [{"role":"system","content":prompt},{"role":"user","content":question}], "stream": True, "temperature": 0.2}
        
        print("\nNa: ", end="", flush=True)
        reponse_full, phrase_buf = "", ""

        #with requests.post(URL_SERVEUR, json=payload, stream=True, timeout=15) as r:
        with requests.post(URL_SERVEUR, json=payload, stream=True, timeout=60) as r:
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

        # Sauvegarde en mémoire si demandé
        if veut_memoriser:
            info = question
            for t in mots_save: info = re.compile(re.escape(t), re.IGNORECASE).sub("", info).strip()
            if len(info) > 3:
                coll_rel.add(documents=[info], ids=[f"rel_{int(time.time())}"])
                print(f"💾 Info mémorisée : {info}")

    except Exception as e:
        print(f"❌ Erreur critique LLM : {e}")


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

# On vérifie simplement si le mot "OK" est présent dans la réponse, peu importe l'émoji
KIWIX_OK = "OK" in status.get("Kiwix (Savoir)", "")

for service, etat in status.items(): 
    print(f"[{etat}] {service}")

if not KIWIX_OK:
    print("⚠️ Attention : Kiwix est détecté comme HORS LIGNE. Les recherches wiki ne fonctionneront pas.")

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_message = on_message

try:
    client.connect(BROKER, 1883)
    client.subscribe([(TOPIC_QUESTION, 0), (TOPIC_APPRENDRE, 0), (TOPIC_RAZ, 0)])
except Exception as e:
    print(f"❌ Connexion Broker Impossible ({BROKER}) : {e}")
    exit(1)

threading.Thread(target=worker_natacha, daemon=True).start()
print(f"🚀 Natacha v33.12ae en ligne. (DB: {CHROMA_DIR})")
client.loop_forever()
