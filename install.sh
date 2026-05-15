#!/bin/bash
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
#
#######################################################
##  Projet Natacha INSTALLATION AUTOMATIQUE DU NOEUD
#######################################################

set -e  # Arrête le script en cas d'erreur

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Vérification de sécurité sur le nom du dossier
if [[ "$(basename "$PWD")" != "Natacha-Project" ]]; then
    echo -e "${YELLOW}Le dossier actuel ne s'appelle pas 'Natacha-Project'.${NC}"
    echo -e "Pour que les services fonctionnent, je vais le renommer..."
    cd ..
    mv -- "$(basename "$PROJECT_ROOT")" "Natacha-Project"
    cd "Natacha-Project"
    PROJECT_ROOT=$(pwd)
    echo -e "${GREEN}Dossier renommé avec succès.${NC}"
fi


echo -e "${GREEN}-------------------------------------------------------"
echo "   Installation du Projet Natacha - Cluster IA"
echo -e "-------------------------------------------------------${NC}"

# Vérification des droits sudo avant de commencer
echo "Vérification des droits d'administration..."
if sudo -v &> /dev/null; then
    echo "Droits sudo validés."
else
    echo -e "${RED}Erreur : Vous devez avoir les droits sudo pour lancer l'installation.${NC}"
    exit 1
fi

echo "Quel module installer sur cette machine ?"
echo "1) L'Oreille"
echo "2) Le Cerveau"
echo "3) La Bouche"
echo "4) Quitter"
read -p "Votre choix [1-4] : " choice

if [ "$choice" -eq 4 ]; then exit 0; fi

PROJECT_ROOT=$(pwd)
CURRENT_USER=$USER # Récupère l'utilisateur qui lance le script

# --- Fonction pour installer le service existant ---
deploy_service() {
    local MODULE_PATH=$1    # ex: ear
    local SERVICE_NAME=$2    # ex: oreille_natacha

    echo -e "${GREEN}Installation du service $SERVICE_NAME...${NC}"
    mkdir -p ~/.config/systemd/user/

    # Copie du fichier depuis ton dossier de scripts vers le dossier systemd utilisateur
    cp "$PROJECT_ROOT/scripts_systemd/$MODULE_PATH/$SERVICE_NAME.service" ~/.config/systemd/user/

    # Remplacement de 'vieil' par l'utilisateur actuel dans le fichier copié
    sed -i "s/vieil/$CURRENT_USER/g" ~/.config/systemd/user/$SERVICE_NAME.service

    # Activation
    systemctl --user daemon-reload
    systemctl --user enable $SERVICE_NAME.service
    echo -e "${GREEN}Service $SERVICE_NAME configuré et activé pour l'utilisateur $CURRENT_USER !${NC}"
}

# --- 1. Miniconda ---
if ! command -v conda &> /dev/null; then
    echo "Installation de Miniconda..."
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
    bash miniconda.sh -b -p $HOME/miniconda3
    $HOME/miniconda3/bin/conda init bash
    export PATH="$HOME/miniconda3/bin:$PATH"
fi

# --- 2. Installation par module ---
case $choice in
    1)
        echo -e "${GREEN}>>> Configuration OREILLE...${NC}"
        sudo apt update && sudo apt install -y ffmpeg gstreamer1.0-tools portaudio19-dev
        conda create -n oreille_natacha python=3.10 -y
        $HOME/miniconda3/envs/oreille_natacha/bin/pip install -r "$PROJECT_ROOT/modules/ear/requirements.txt"
        deploy_service "ear" "oreille_natacha"
        ;;
    2)
        echo -e "${GREEN}>>> Configuration CERVEAU...${NC}"
        sudo apt update && sudo apt install -y build-essential cmake
        conda create -n cerveau_natacha python=3.10 -y
        $HOME/miniconda3/envs/cerveau_natacha/bin/pip install -r "$PROJECT_ROOT/modules/brain/requirements.txt"
        deploy_service "brain" "cerveau_natacha"
        echo -e "${YELLOW}Nota: N'oubliez pas de compiler llama.cpp manuellement.${NC}"
        ;;
    3)
        echo -e "${GREEN}>>> Configuration BOUCHE...${NC}"
        sudo apt update && sudo apt install -y gstreamer1.0-tools alsa-utils
        conda create -n bouche_natacha python=3.10 -y
        $HOME/miniconda3/envs/bouche_natacha/bin/pip install -r "$PROJECT_ROOT/modules/mouth/requirements.txt"
        deploy_service "mouth" "bouche_natacha"
        ;;
esac

# --- 3. Finalisation ---
sudo loginctl enable-linger $USER
echo -e "${GREEN}Installation terminée ! Pensez à vérifier vos fichiers dans /secrets.${NC}"
