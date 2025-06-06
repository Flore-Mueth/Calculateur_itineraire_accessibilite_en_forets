from flask import Flask, request, jsonify
from flask_cors import CORS
from calculateur_itineraire import calculate_route, load_network, get_network_edges
import traceback
import osmnx as ox
import pickle

app = Flask(__name__)
CORS(app)

# Load the network once at startup
print("Chargement du réseau routier...")
G = load_network()
print("Réseau routier chargé avec succès!")

@app.route('/process', methods=['POST'])
def process_coordinates():
    try:
        data = request.get_json()
        print("Données reçues:", data)  # Log pour debug
        
        lat1 = float(data.get('lat1'))
        lng1 = float(data.get('lng1'))
        lat2 = float(data.get('lat2'))
        lng2 = float(data.get('lng2'))

        if any(v is None for v in [lat1, lng1, lat2, lng2]):
            return jsonify({'message': 'Toutes les coordonnées doivent être fournies.'}), 400

        print(f"Calcul de route: de ({lat1}, {lng1}) à ({lat2}, {lng2})")
        
        # Appel de la nouvelle fonction qui retourne plusieurs routes
        result = calculate_route(G, lat1, lng1, lat2, lng2, k=5)

        routes = result.get("routes", [])
        message = result.get("message", "Aucun message reçu")

        if not routes:
            return jsonify({
                "message": message,
                "routes": [],
                "success": False
            })

        print(f"Routes calculées: {len(routes)} itinéraire(s) trouvé(s)")
        
        # Log des détails de chaque route pour debug
        for i, route in enumerate(routes):
            print(f"Route {i+1}: {route['length']}m, {route['travel_time']}min, {len(route['geometry'])} points")

        # Validation des données avant envoi
        processed_routes = []
        for i, route in enumerate(routes):
            # S'assurer que tous les champs nécessaires sont présents
            processed_route = {
                'geometry': route.get('geometry', []),
                'length': int(route.get('length', 0)),  # S'assurer que c'est un entier
                'travel_time': round(float(route.get('travel_time', 0)), 1),  # Arrondir à 1 décimale
                'distance_to_coord': round(float(route.get('distance_to_coord', 0)), 1)
            }
            
            # Validation de la géométrie
            if not processed_route['geometry'] or len(processed_route['geometry']) < 2:
                print(f"Attention: Route {i+1} a une géométrie invalide")
                continue
                
            processed_routes.append(processed_route)

        if not processed_routes:
            raise ValueError("Aucun itinéraire valide trouvé après traitement")

        # Trier les routes par temps de trajet (meilleure en premier)
        processed_routes.sort(key=lambda x: x['travel_time'])

        return jsonify({
            "message": f"{len(processed_routes)} itinéraire(s) trouvé(s). Meilleur temps: {processed_routes[0]['travel_time']} min",
            "routes": processed_routes,
            "success": True
        })

    except ValueError as ve:
        print("Erreur de valeur:", str(ve))
        return jsonify({
            'message': f'Erreur de calcul: {str(ve)}',
            'success': False
        }), 400
        
    except Exception as e:
        print("Erreur inattendue:", str(e))
        traceback.print_exc()  # Affiche la trace d'erreur complète
        return jsonify({
            'message': f'Erreur serveur: {str(e)}',
            'success': False
        }), 500


# Fonction de fallback pour compatibilité avec l'ancienne version
@app.route('/process_single', methods=['POST'])
def process_coordinates_single():
    """
    Version de compatibilité qui retourne une seule route (la meilleure)
    au format de l'ancienne API
    """
    try:
        data = request.get_json()
        lat1 = float(data.get('lat1'))
        lng1 = float(data.get('lng1'))
        lat2 = float(data.get('lat2'))
        lng2 = float(data.get('lng2'))

        if any(v is None for v in [lat1, lng1, lat2, lng2]):
            return jsonify({'message': 'Toutes les coordonnées doivent être fournies.'}), 400

        # Obtenir toutes les routes et prendre la meilleure
        routes = calculate_route(G, lat1, lng1, lat2, lng2, k=5)
        if not routes:
            raise ValueError("Aucun itinéraire trouvé")
            
        # Prendre la meilleure route (première après tri par temps)
        best_route = min(routes, key=lambda x: x['travel_time'])
        
        # Convertir au format de l'ancienne API
        route_geometry_list = best_route['geometry']
        
        return jsonify({
            'message': f'Longueur du trajet: {best_route["length"]} mètres | Temps estimé: {best_route["travel_time"]} minutes',
            'route_geometry': route_geometry_list,
            'distance': best_route['length'],
            'travel_time': best_route['travel_time'],
            'distance_to_coord': round(float(best_route.get('distance_to_coord', 0)), 1),
            'success': True
        })

    except Exception as e:
        print("Erreur:", str(e))
        traceback.print_exc()
        return jsonify({'message': f'Erreur: {str(e)}', 'success': False}), 500

@app.route('/network', methods=['GET'])
def get_network():
    try:
        # Extraire les coordonnées des arêtes du réseau
        edges = get_network_edges(G)
        
        return jsonify({
            'edges': edges
        })
    
    except Exception as e:
        print("Erreur lors de la récupération du réseau:", str(e))
        traceback.print_exc()
        return jsonify({'message': f'Erreur: {str(e)}'}), 500
    
@app.route("/delete_edges", methods=["POST"])
def delete_edges():
    global G
    try:
        data = request.get_json()
        edges_to_delete = data.get("edges", [])
        print("Arêtes reçues pour suppression :", edges_to_delete)

        deleted = 0
        for edge in edges_to_delete:
            u = edge.get("u")
            v = edge.get("v")

            if u is None or v is None:
                continue

            if G.has_edge(u, v):
                G.remove_edge(u, v)
                print(f"Arête supprimée : {u} → {v}")
                deleted += 1
            if G.has_edge(v, u):
                G.remove_edge(v, u)
                print(f"Arête supprimée : {v} → {u}")
                deleted += 1

        return jsonify({"message": f"{deleted} arêtes supprimées."})
    except Exception as e:
        print("Erreur lors de la suppression des arêtes:", e)
        return jsonify({"message": "Erreur interne"}), 500

@app.route("/save_network", methods=["POST"])
def save_network():
    global G
    try:
        # Sauvegarde au format pickle
        with open("Vaud.pkl", "wb") as f:
            pickle.dump(G, f)

        # Sauvegarde au format GraphML
        import osmnx as ox
        ox.save_graphml(G, filepath="Vaud.graphml")

        return jsonify({"message": "Le réseau a été enregistré au format .pkl et .graphml avec succès."})
    except Exception as e:
        print("Erreur lors de la sauvegarde du réseau:", e)
        return jsonify({"message": "Erreur lors de la sauvegarde."}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')