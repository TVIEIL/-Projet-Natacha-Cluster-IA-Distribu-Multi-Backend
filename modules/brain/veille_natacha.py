import feedparser
import paho.mqtt.client as mqtt
import time
import requests
import re

# Configuration
BROKER = "127.0.0.1"
TOPIC_APPRENDRE = "natacha/apprendre"
FEEDS = [
    "https://cnes.fr/fr/rss.xml", "https://www.esa.int/rssfeed/France",
    "https://www.france24.com/fr/rss", "https://www.lemonde.fr/international/rss_full.xml",
    "https://www.courrierinternational.com/feed/all/rss.xml", "https://next.ink/feed/",
    "https://www.radioamateur.org/rss/news.xml", "https://lenergeek.com/feed/",
    "https://www.techniques-ingenieur.fr/actualite/feed/",
    "https://www.science-et-vie.com/feed" # La petite touche de curiosité en plus
]

def internet_disponible():
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except:
        return False

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def scan_news():
    client = mqtt.Client()
    try:
        client.connect(BROKER, 1883, 60)
        print("🔭 Connexion au Broker MQTT réussie.")
        
        for url in FEEDS:
            feed = feedparser.parse(url)
            # On prend les 2 plus fraîches pour ne pas saturer ChromaDB
            for entry in feed.entries[:2]: 
                description = clean_html(entry.get('description', ''))
                info = f"ACTU {time.strftime('%Y-%m-%d')} : {entry.title}. {description}"
                
                print(f"📡 Envoi à Natacha : {entry.title[:50]}...")
                client.publish(TOPIC_APPRENDRE, info)
                time.sleep(1) 
        
        client.disconnect()
    except Exception as e:
        print(f"❌ Erreur MQTT ou Scan : {e}")

if __name__ == "__main__":
    print("🚀 Module de veille activé.")
    while True:
        if internet_disponible():
            print("🌐 Internet OK. Mise à jour des connaissances...")
            scan_news()
            # On attend 6 heures avant le prochain scan (21600 secondes)
            time.sleep(21600)
        else:
            print("☁️ Pas d'internet. Nouvelle tentative dans 5 minutes...")
            time.sleep(300)
