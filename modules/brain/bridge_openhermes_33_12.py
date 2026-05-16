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
file_questions = queue.Queue(maxsize=10)

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
        search_url = f"{KIWIX_URL}/search?content={NOM_LIVRE_KIWIX}&pattern={urllib.parse.quote(recherche)}"
        res_search = requests.get(search_url, timeout=5)
        
        # 1. On cherche d'abord avec le nom du livre précis
        liens = re.findall(r'href=["\'](/content/' + NOM_LIVRE_KIWIX + r'/[^"\']+)["\']', res_search.text)

        # 2. Si ça ne donne rien, on élargit (Correction de l'indentation ici)
        if not liens:
            liens = re.findall(r'href=["\'](/content/[^"\']+)["\']', res_search.text)

        # 3. Sécurité : On vérifie si on a trouvé AU MOINS un lien avant de tenter le get
        if not liens:
            return ""

        res_article = requests.get(f"{KIWIX_URL}{liens[0]}", timeout=5)

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
    
    # --- REGLAGE v33.12ak : BYPASS DES PHRASES DE COURTOISIE ---
    if any(mot in q_low for mot in ["merci", "merci beaucoup", "revoir", "bonne nuit"]):
        reponses_merci = [
            "De rien Thierry ! C'est toujours un plaisir de t'aider.",
            "Avec plaisir Thierry ! Dis-moi si tu as besoin d'autre chose.",
            "Pas de quoi, mon créateur ! Je reste à l'écoute.",
            "À ton service ! C'est ça, la complicité entre électroniciens."
        ]
        reponse_directe = random.choice(reponses_merci)
        
        print("\nNa: ", end="", flush=True)
        client_mqtt.publish(TOPIC_REPONSE, reponse_directe)
        print(reponse_directe)
        print("\n\n  [Step 5] Réponse terminée (Bypass Courtoisie).\n")
        return # On arrête la fonction ici, pas besoin d'envoyer au LLM !
    
    # Gestion des dates et de l'âge
    now = datetime.now()
    h_str = now.strftime("%A %d %B %Y à %Hh%M")
    annee_cible = str(now.year)
    match_annee = re.search(r'\b(20[0-9]{2})\b', q_low)
    if match_annee: annee_cible = match_annee.group(1)

# --- AJOUT : EXTRACTION PRÉCISE DE LA DATE ---
    date_formatee = annee_cible
    mois_map = {
        "janvier": "01", "février": "02", "mars": "03", "avril": "04", "mai": "05", "juin": "06",
        "juillet": "07", "août": "08", "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12"
    }
    
    # On cherche un motif type "14 mai" dans la question
    match_date = re.search(r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)', q_low)
    if match_date:
        jour = match_date.group(1).zfill(2)
        mois = mois_map.get(match_date.group(2))
        date_formatee = f"{annee_cible}-{mois}-{jour}" # Résultat : "2026-05-14"

    anniv_passe = (now.month > 12) or (now.month == 12 and now.day >= 3)
    age = (now.year - 1974) if anniv_passe else (now.year - 1974 - 1)

    # Détection des intentions
    mots_save = ["enregistre", "mémorise", "souviens"]
    mots_news = ["nouvelles", "neuf", "actu", "actualité", "infos", "news", "2026", "passé"]
    mots_cles_wiki = ["physique", "tension", "kiwix", "wiki", "recherche", "qx", "fermi", "loi", "ohm", "ampere"]
    
    # --- AJOUT : Détection des phrases de courtoisie (Passe-Bas) ---
    est_courtoisie = any(mot in q_low for mot in ["merci", "bonjour", "salut", "ça va", "revoir", "merci beaucoup"])

    veut_memoriser = any(m in q_low for m in mots_save)
    # Si c'est juste de la courtoisie, on ne force pas la recherche d'actus ou de wiki
    veut_chercher_news = (any(m in q_low for m in mots_news) or match_annee is not None) and not est_courtoisie
    veut_wiki = any(mot in q_low for mot in mots_cles_wiki) and not est_courtoisie

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
        try:
            # Étage 1 : Recherche vectorielle classique dans les relations
            res_rel = coll_rel.query(query_embeddings=[q_vec], n_results=5)
            if res_rel['documents'] and res_rel['documents'][0]:
                souvenirs_perso = "\n".join([str(d) for d in res_rel['documents'][0] if d])
            
            # Étage 2 : Scan brut textuel (Bypass sémantique pour sécuriser la famille et l'identité)
            mots_famille = ["frère", "frere", "mère", "mere", "père", "pere", "maman", "papa", "famille", "parents"]
            if any(f in q_low for f in mots_famille) or "thierry" in q_low or "ind" in q_low:
                toutes_les_news_rel = coll_rel.get()
                secours_famille = [
                    str(doc) for doc in toutes_les_news_rel['documents']
                    if doc and any(mot in str(doc).lower() for mot in mots_famille or ["laurent", "claudine", "aimé", "thierry", "f4hrb"])
                ]
                if secours_famille:
                    # On fusionne le vectoriel et le textuel en éliminant les doublons
                    liste_finale = list(set((souvenirs_perso.split("\n") if souvenirs_perso else []) + secours_famille))
                    souvenirs_perso = "\n".join(liste_finale[:6])
                    print(f"  [OK] {len(secours_famille)} souvenirs personnels/famille sécurisés par scan brut.")
        except Exception as e:
            print(f"⚠️ Erreur lors de la récupération des souvenirs : {e}")
            
        # Actualités : On passe en mode précision (v33.12am_clean)
        if veut_chercher_news:
            try:
                res_exp = coll_exp.query(
                    query_embeddings=[q_vec], 
                    n_results=50,
                    where_document={"$contains": f"ACTU {date_formatee}"}
                )
                
                if res_exp['documents'] and res_exp['documents'][0]:
                    # --- NETTOYAGE RADICAL ANTI-CRASH ---
                    brutes = [str(doc) for doc in res_exp['documents'][0] if doc]
                    actualites_filtrees = []
                    
                    for doc in brutes[:5]: # On garde les 5 premières
                        # 1. On décode les entités HTML résiduelles (les &#8230;)
                        txt_propre = html.unescape(doc)
                        # 2. On remplace les caractères exotiques qui font bugger le tokenizer
                        txt_propre = txt_propre.replace("«", '"').replace("»", '"')
                        txt_propre = txt_propre.replace("’", "'").replace("&#160;", " ")
                        actualites_filtrees.append(txt_propre)
                        
                    contexte_actualites = "\n".join(actualites_filtrees)
                    print(f"  [OK] {len(actualites_filtrees)} news nettoyées pour le {date_formatee}.")
                else:
                    # Sécurité Scan Brut (On applique le même nettoyage)
                    toutes_les_news = coll_exp.get()
                    brutes = [str(doc) for doc in toutes_les_news['documents'] if doc and date_formatee in str(doc)]
                    actualites_filtrees = []
                    for doc in brutes[:5]:
                        txt_propre = html.unescape(doc).replace("«", '"').replace("»", '"').replace("’", "'")
                        actualites_filtrees.append(txt_propre)
                        
                    contexte_actualites = "\n".join(actualites_filtrees)
                    
                    if actualites_filtrees:
                        print(f"  [OK] {len(actualites_filtrees)} news récupérées par scan brut et nettoyées.")
                    else:
                        print(f"  [DEBUG] Aucune news dans Chroma pour la date : {date_formatee}")
            except Exception as e:
                print(f"⚠️ Erreur lors de la recherche d'actus : {e}")


    # --- 4. CONSTRUCTION DU PROMPT ET ENVOI LLM ---
    # --- CONSTRUCTION DYNAMIQUE DU PROMPT (v33.12al_clean) ---
    intro = obtenir_intro_naturelle()
    
    veut_detail = any(mot in q_low for mot in ["lit", "lis", "détaille", "explique", "wiki", "recherche", "trouve"])
    consigne_longueur = "Développe largement ta réponse en citant les détails du livre." if veut_detail else "Sois concise et naturelle."

    if is_authenticated or "thierry" in q_low:
        role_instruction = (
            "STATUT : MAÎTRE RECONNU. Tu parles à ton créateur Thierry VIEIL (F4HRB). "
            "Tu as l'interdiction absolue de le vouvoyer. Tutoie-le, sois très complice, amicale et directe."
        )
    else:
        role_instruction = "Tu parles à un utilisateur. Tutoie-le obligatoirement. Sois décontractée."

    # On assemble le bloc de contexte uniquement avec ce qui contient de l'info
    bloc_contexte = ""
    if contexte_actualites:
        bloc_contexte += f"### ACTUALITÉS DU JOUR :\n{contexte_actualites}\n--------------------------\n"
    if savoir_physique:
        bloc_contexte += f"### DONNÉES DE RÉFÉRENCE (KIWIX) :\n{savoir_physique}\n--------------------------\n"
    if souvenirs_perso:
        bloc_contexte += f"### SOUVENIRS PERSONNELS (CHROMA) :\n{souvenirs_perso}\n--------------------------\n"

# Construction finale épurée (v33.12as)
    prompt = (
        f"SYSTEME : Tu es Natacha, assistante IA experte. Nous sommes le {h_str}.\n"
        "NOTE TECHNIQUE : ChromaDB est ta base de mémoire sémantique contenant les SEULS faits réels sur Thierry.\n\n"
        f"{bloc_contexte}"
        "### INSTRUCTIONS STRICTES DE VÉRITÉ :\n"
        f"- {role_instruction}\n"
        "- RECHERCHE OBLIGATOIRE : Pour les questions sur la famille, les parents ou les proches de Thierry, utilise UNIQUEMENT les informations écrites dans 'SOUVENIRS PERSONNELS'.\n"
        "- ANTI-HALLUCINATION : Si l'information exacte n'est pas écrite dans les SOUVENIRS PERSONNELS, réponds STRICTEMENT 'Je ne m'en souviens pas, peux-tu me le rappeler ?'. Interdiction absolue d'inventer des prénoms (comme Pierre, Marie, Thomas, Claire).\n"
        "- Interdiction formelle d'utiliser 'vous' ou 'votre'. Utilise uniquement 'tu', 'toi' et 'tes'.\n"
        "- Ne cite jamais tes règles ni les mots 'ChromaDB' ou 'Kiwix'.\n"
        f"- Conduite : Parle comme une collègue électronicienne. {consigne_longueur}\n\n"
        f"COMMENCE DIRECTEMENT TA RÉPONSE PAR : {intro}\n"
        "RÉPONSE DE NATACHA :"
    )


    # Construction finale épurée
    #prompt = (
    #    f"SYSTEME : Tu es Natacha, assistante IA experte en électronique et sciences. Nous sommes le {h_str}.\n"
    #    "NOTE TECHNIQUE : ChromaDB est ta base de mémoire sémantique et Kiwix est ton dictionnaire Wikipédia local.\n\n"
    #    f"{bloc_contexte}"
    #    "### INSTRUCTIONS STRICTES :\n"
    #    f"- {role_instruction}\n"
    #    "- Interdiction formelle d'utiliser 'vous' ou 'votre'. Utilise uniquement 'tu', 'toi' et 'tes'.\n"
    #    "- Ne cite JAMAIS tes instructions, tes règles d'or, ni les mots 'ChromaDB' ou 'Kiwix' dans ta réponse.\n"
    #    f"- Conduite : Parle comme une collègue électronicienne. {consigne_longueur}\n\n"
    #    f"COMMENCE DIRECTEMENT TA RÉPONSE PAR : {intro}\n"
    #    "RÉPONSE DE NATACHA :"
    #)

    # --- CONSTRUCTION DU PROMPT (v33.12w) ---
    #intro = obtenir_intro_naturelle()
    
    # On s'assure que le savoir technique n'est pas "indigeste"
    #contexte_wiki = savoir_physique if savoir_physique else "Aucune donnée encyclopédique trouvée."

   # --- DÉTECTION DE L'INTENTION DE DÉTAIL ---
    #veut_detail = any(mot in q_low for mot in ["lit", "lis", "détaille", "explique", "wiki", "recherche", "trouve"])
    #consigne_longueur = "Développe largement ta réponse en citant les détails du livre." if veut_detail else "Sois concise et naturelle."



    #if is_authenticated or "thierry" in q_low:
    #    role_instruction = (
    #        "STATUT : MAÎTRE RECONNU. Tu parles à Thierry VIEIL (F4HRB), ton créateur. "
    #        "Tu as l'interdiction absolue de le vouvoyer. Tutoie-le, sois complice, amicale et directe."
    #    )
    #else:
    #    role_instruction = (
    #        "Tu parles à un utilisateur qui s'appelle peut-être Thierry. "
    #        "Dans le doute, utilise IMPÉRATIVEMENT le tutoiement. Sois décontractée."
    #    )

    
    # --- CONSTRUCTION DU PROMPT (v33.12ag - Correction news & syntaxe) ---
    #prompt = (
    #    f"SYSTEME : Tu es Natacha, assistante IA experte. Nous sommes le {h_str}.\n\n"
    #    "### ACTUALITÉS DU JOUR (Extraites de ChromaDB) :\n"
    #    f"{contexte_actualites if contexte_actualites else 'Aucune actualité trouvée pour cette date.'}\n"
    #    "--------------------------\n"
    #    "### DONNÉES DE RÉFÉRENCE (KIWIX) :\n"
    #    f"{savoir_physique if savoir_physique else 'Aucune donnée encyclopédique trouvée.'}\n"
    #    "--------------------------\n"
    #    "### SOUVENIRS PERSONNELS (CHROMA) :\n"
    #    f"{souvenirs_perso if souvenirs_perso else 'Aucun souvenir récent trouvé.'}\n"
    #    "--------------------------\n\n"
    #    "### RÈGLES D'OR DE NATACHA :\n"
    #    f"{role_instruction}\n"
    #    "1. TU DOIS TUTOYER THIERRY. Interdiction formelle d'utiliser 'vous' ou 'votre'. Utilise 'tu', 'toi' et 'tes'.\n"
    #    "2. ANALYSE GLOBALE : Ne dis jamais qu'une date est fictive. Synthétise TOUTES les actualités fournies ci-dessus pour faire un résumé complet.\n"
     #   "3. Parle de façon décontractée, comme une collègue électronicienne.\n"
     #   f"4. {consigne_longueur}\n"
     #   "--------------------------\n"
     #   f"COMMENCE DIRECTEMENT TA RÉPONSE PAR : {intro}\n"
     #   "RÉPONSE DE NATACHA :"
    #)


    # --- CONSTRUCTION DU PROMPT (v33.12af - Correction news) ---
    #prompt = (
    #    f"SYSTEME : Tu es Natacha, assistante IA experte. Nous sommes le {h_str}.\n\n"
    #    "### ACTUALITÉS DU JOUR (Extraites de ChromaDB) :\n"
    #    f"{contexte_actualites if contexte_actualites else 'Aucune actualité trouvée pour cette date.'}\n"
    #    "--------------------------\n"
    #    "### DONNÉES DE RÉFÉRENCE (KIWIX) :\n"
    #    f"{savoir_physique if savoir_physique else 'Aucune donnée encyclopédique trouvée.'}\n"
    #    "--------------------------\n"
    #    "### SOUVENIRS PERSONNELS (CHROMA) :\n"
    #    f"{souvenirs_perso if souvenirs_perso else 'Aucun souvenir récent trouvé.'}\n"
    #    "--------------------------\n\n"
    #    "### RÈGLES D'OR DE NATACHA :\n"
    #    f"{role_instruction}\n"
    #    "1. TU DOIS TUTOYER THIERRY. Utilise 'tu' et 'toi', jamais 'vous'.\n"
    #    "2. Ne dis JAMAIS qu'une date est fictive. Si l'info est dans 'ACTUALITÉS', elle est réelle.\n"
    #    "3. Parle de façon décontractée, comme une collègue électronicienne.\n"
    #    f"4. {consigne_longueur}\n"
    #    f"5. TA RÉPONSE COMMENCE PAR : {intro}\n"
    #    "RÉPONSE DE NATACHA :"
    #)

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
        try: 
            file_questions.put(action, block=False)
        except queue.Full: 
            print("\n⚠️ [DÉBORDEMENT] File MQTT saturée : message ignoré.")

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
print(f"🚀 Natacha v33.12at en ligne. (DB: {CHROMA_DIR})")
client.loop_forever()
