import chromadb
from chromadb.utils import embedding_functions

# --- CONFIGURATION ---
PATH_MEMOIRE = "./memoire_chroma"
chroma_client = chromadb.PersistentClient(path=PATH_MEMOIRE)
emb_fn = embedding_functions.DefaultEmbeddingFunction()

def nettoyer_collection(nom_collection):
    print(f"\n--- 🔍 Analyse de la collection : {nom_collection} ---")
    coll = chroma_client.get_or_create_collection(name=nom_collection, embedding_function=emb_fn)
    
    # Récupérer TOUT le contenu
    donnees = coll.get()
    ids = donnees['ids']
    documents = donnees['documents']
    
    if not ids:
        print("La collection est vide.")
        return

    vu = {} # Dictionnaire {contenu_normalise: id_a_garder}
    doublons = []

    for i in range(len(documents)):
        texte_original = documents[i]
        id_doc = ids[i]
        
        # NORMALISATION : 
        # On prend tout ce qui est APRÈS le premier ":" pour ignorer la date
        if ":" in texte_original:
            contenu_normalise = texte_original.split(":", 1)[1].strip()
        else:
            contenu_normalise = texte_original.strip()

        # Comparaison du contenu épuré
        if contenu_normalise in vu:
            doublons.append(id_doc)
            print(f"  [X] Doublon détecté : '{contenu_normalise[:60]}...'")
        else:
            vu[contenu_normalise] = id_doc

    # Suppression effective dans ChromaDB
    if doublons:
        coll.delete(ids=doublons)
        print(f"✅ {len(doublons)} doublons supprimés de la collection.")
    else:
        print("✨ Aucun doublon trouvé (le contenu épuré est déjà unique).")
    
    print(f"📊 Total après nettoyage : {len(ids) - len(doublons)} entrées.")

if __name__ == "__main__":
    nettoyer_collection("natacha_relation")
    nettoyer_collection("natacha_expertise")
