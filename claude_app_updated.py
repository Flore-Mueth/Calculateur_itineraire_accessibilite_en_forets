from flask import Flask, request, jsonify
from flask_cors import CORS
from claude_interface_code_updated import calculate_route, load_network, get_network_edges
import traceback

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
        route_geometry, route_length, travel_time = calculate_route(G, lat1, lng1, lat2, lng2)
        print(f"Route calculée, longueur: {route_length} m, temps: {travel_time} min")

        # Convertir route_geometry en liste pour la sérialisation JSON
        route_geometry_list = [[float(x), float(y)] for x, y in route_geometry]

        return jsonify({
            'message': f'Longueur du trajet: {route_length} mètres | Temps estimé: {travel_time} minutes',
            'route_geometry': route_geometry_list,
            'route_length': route_length,
            'travel_time': travel_time
        })

    except Exception as e:
        print("Erreur:", str(e))
        traceback.print_exc()  # Affiche la trace d'erreur complète
        return jsonify({'message': f'Erreur: {str(e)}'}), 500

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')