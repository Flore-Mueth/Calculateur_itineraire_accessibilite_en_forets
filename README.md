# Outil de calcul de l’accessibilité des massifs forestiers en cas d’incendie de forêt

## Context du projet

Avec l’intensification des sécheresses liées au changement climatique, les forêts deviennent de plus en plus vulnérables aux incendies. Même si le canton de Vaud n’est pas encore aussi exposé que d’autres régions, il est crucial d’anticiper des événements potentiellement plus fréquents et violents afin de limiter les dégâts.

L’un des enjeux clés en cas d’incendie est la rapidité d’accès aux zones touchées. Certaines parties des massifs forestiers disposent d’un bon réseau d’accès pour les véhicules d’intervention, tandis que d’autres restent difficilement accessibles, voire uniquement par voie aérienne.

Ce projet propose un prototype d’outil, basé sur les Systèmes d’Information Géographique (SIG), permettant de calculer des itinéraires optimisés vers un point donné en forêt. Le réseau routier utilisé est issu d’OpenStreetMap, enrichi par nos recherches pour distinguer les routes praticables par des camions d’intervention de celles qui ne le sont pas. Ce réseau peut être modifié directement par l’utilisateur de l’interface, afin de refléter une connaissance de terrain plus précise et à jour.

Il vise à fournir un appui concret à la planification et à l’efficacité des interventions d’urgence en milieu forestier.

## Interface

### Concept

L’interface prend la forme d’un site web permettant de simuler une intervention en cas d’incendie de forêt. L’utilisateur saisit les coordonnées de la caserne de départ et celles du lieu d’intervention. L’outil calcule alors l’itinéraire le plus rapide possible en camion de pompier et l’affiche sur une carte.

Le calcul se base sur un graphe routier dérivé d’OpenStreetMap, enrichi par nos recherches pour distinguer les routes praticables par des camions. L’algorithme d’optimisation utilise le temps de parcours estimé, calculé à partir des vitesses maximales connues ou estimées sur chaque tronçon.

Si aucun itinéraire praticable n’est trouvé, un message informe l’utilisateur qu’une intervention terrestre est impossible et qu’une solution aérienne est nécessaire.

La recherche du point d’arrivée le plus proche dans le réseau routier ne tient pas compte de la précision géographique et des contraintes de terrain (par exemple, un accès en ligne droite peut être bloqué par un relief infranchissable). C'est porquoi plusieurs nœuds proches sont évalués pour assurer la faisabilité de l’accès.

Enfin, une fonctionnalité permet à l’utilisateur de modifier le réseau routier directement dans l’interface, en fonction de sa connaissance du terrain : suppression de tronçons, ajustement des vitesses, etc., afin de refléter au mieux la réalité opérationnelle.

### Utilisation

Pour utiliser l’interface localement, il faut d’abord télécharger les fichiers suivants :

- `preparation_reseau.ipynb`
- `interface.html`
- `backend_app.py`
- `calculateur_itineraire.py`
- `requirements.txt`

Et installer toutes les dépendances en une seule commande :

```bash
pip install -r requirements.txt
```

#### 1. Préparation du réseau

Lancez le notebook `preparation_reseau.ipynb`. Celui-ci télécharge le réseau routier du canton de Vaud depuis OpenStreetMap et le modifie en fonction des contraintes liées à l’accessibilité pour les véhicules d’intervention.

Ce script génère deux fichiers :

- `Vaud.graphml` : utilisé par l’interface pour le calcul d’itinéraire.
- `Vaud.gpkg` : utilisable dans QGIS pour visualiser le réseau.

#### 2. Lancement de l’interface

Exécutez le fichier `backend_app.py` pour activer le serveur backend :

```bash
python backend_app.py
```

Une fois le serveur correctement lancé, vous devriez voir ce message dans le terminal :

* Debugger is active!
* Debugger PIN: 931-435-741

Attention : Le chargement initial peut prendre un certain temps, car le réseau du canton de Vaud est relativement volumineux.

#### 3. Utilisation de l’interface

Une fois le backend lancé, ouvrez le fichier `interface.html` dans un navigateur web. L’interface est alors prête à être utilisée pour simuler des itinéraires d’intervention.

