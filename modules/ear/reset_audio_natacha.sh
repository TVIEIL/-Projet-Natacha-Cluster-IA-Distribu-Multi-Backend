#!/bin/bash

echo "🚀 Initialisation du Grand Reset Audio (ALSA + PulseAudio + PipeWire)..."

# 1. Niveau Kernel : ALSA
echo "--- 1/3 Réinitialisation ALSA ---"
sudo alsa force-reload

# 2. Niveau Serveur : PipeWire / PulseAudio / WirePlumber
# Sur Ubuntu 24.04, on redémarre les services utilisateurs
echo "--- 2/3 Redémarrage de la pile PipeWire & WirePlumber ---"
systemctl --user restart pipewire pipewire-pulse wireplumber

# On laisse 2 secondes aux services pour se stabiliser
sleep 2

# 3. Niveau Réglages : Unmute et Volume
echo "--- 3/3 Configuration des niveaux ---"
# On utilise l'alias universel @DEFAULT_AUDIO_SINK@ pour ne pas dépendre des IDs
wpctl set-mute @DEFAULT_AUDIO_SINK@ 0
wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.50

# 4. Finalisation : Reconnexion du service Natacha
echo "--- 🛠️  Relance du service GStreamer Natacha ---"
sudo systemctl restart gstream-natacha

echo "---"
echo "✅ Système audio réinitialisé !"
echo "📊 État actuel de l'arborescence :"
wpctl status | grep -A 10 "Audio"
