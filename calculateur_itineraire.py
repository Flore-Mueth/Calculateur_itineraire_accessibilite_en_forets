import networkx as nx
import osmnx as ox
import os
import pickle
from shapely.geometry import Point
import pandas as pd
import traceback

NETWORK_FILE = "Vaud.graphml"
PICKLE_FILE = "Vaud.pkl"  # Un format plus efficace pour stocker le graphe

def load_network():
    """
    Charge le réseau depuis un fichier s'il existe, sinon exécute le notebook 
    preparation_reseau.ipynb pour télécharger et préparer le réseau.
    Utilise pickle pour un chargement plus rapide.
    """
    # Essayer d'abord avec pickle pour un chargement plus rapide
    if os.path.exists(PICKLE_FILE):
        print(f"Chargement du réseau depuis {PICKLE_FILE}")
        with open(PICKLE_FILE, 'rb') as f:
            G = pickle.load(f)
        return G
    
    # Sinon, essayer avec GraphML
    elif os.path.exists(NETWORK_FILE):
        print(f"Chargement du réseau depuis {NETWORK_FILE}")
        G = ox.load_graphml(NETWORK_FILE)
        # Sauvegarder au format pickle pour la prochaine fois
        with open(PICKLE_FILE, 'wb') as f:
            pickle.dump(G, f)
        return G
    
    # Si aucun fichier n'existe, exécuter le notebook pour préparer le réseau
    else:
        print("Aucun fichier réseau trouvé. Exécution du notebook pour préparer le réseau...")
        # notebook_path = "preparation_reseau.ipynb"
        notebook_path = "preparation_reseau.ipynb"

        
        if os.path.exists(notebook_path):
            try:
                import subprocess
                print(f"Exécution du notebook {notebook_path}...")
                result = subprocess.run(["jupyter", "nbconvert", "--execute", "--to", "notebook", 
                                       "--inplace", notebook_path], 
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("Notebook exécuté avec succès, tentative de chargement du réseau...")
                    # Tenter de charger le réseau après l'exécution du notebook
                    if os.path.exists(PICKLE_FILE):
                        with open(PICKLE_FILE, 'rb') as f:
                            G = pickle.load(f)
                        return G
                    elif os.path.exists(NETWORK_FILE):
                        G = ox.load_graphml(NETWORK_FILE)
                        # Sauvegarder au format pickle pour la prochaine fois
                        with open(PICKLE_FILE, 'wb') as f:
                            pickle.dump(G, f)
                        return G
                    else:
                        raise Exception("Aucun fichier réseau trouvé après l'exécution du notebook")
                else:
                    print(f"Erreur lors de l'exécution du notebook: {result.stderr}")
                    raise Exception("Échec de l'exécution du notebook")
            except Exception as e:
                print(f"Erreur lors de l'exécution du notebook: {e}")
                raise Exception("Impossible de charger ou créer le réseau routier")
        else:
            print(f"Le fichier notebook {notebook_path} n'existe pas")
            raise Exception("Fichier notebook de préparation du réseau introuvable")

def calculate_route(G, lat1, lng1, lat2, lng2, k=5):
    """
    Calcule jusqu'à k itinéraires vers les k nœuds les plus proches du point d'arrivée.
    Retourne une liste d'itinéraires avec leur géométrie, longueur et temps estimé.
    """
    try:
        # Trouver le nœud le plus proche du point de départ
        orig = ox.nearest_nodes(G, lng1, lat1)
        print(f"Nœud origine trouvé: {orig}")

        # Convertir le graphe en GeoDataFrame pour les nœuds
        gdf_nodes = ox.graph_to_gdfs(G, edges=False)
        
        # Créer un point pour la destination
        dest_point = Point(lng2, lat2)
        
        # Calculer la distance de chaque nœud à la destination
        gdf_nodes['dist_to_dest'] = gdf_nodes['geometry'].distance(dest_point)
        
        # Obtenir les k nœuds les plus proches de la destination
        closest_nodes = gdf_nodes.sort_values('dist_to_dest').index[:k].tolist()
        print(f"Nœuds destination candidats: {closest_nodes[:3]}...")  # Log des 3 premiers

        all_routes = []
        successful_routes = 0

        for i, dest in enumerate(closest_nodes):
            try:
                print(f"Calcul route {i+1}/{k} vers nœud {dest}")
                
                # Calculer le chemin le plus court
                route = ox.routing.shortest_path(G, orig, dest, weight="travel_time")
                
                if not route or len(route) < 2:
                    print(f"  -> Aucun chemin trouvé vers le nœud {dest}")
                    continue

                # Initialiser les métriques
                route_length = 0
                travel_time = 0
                route_geometry = []

                # Parcourir chaque segment du chemin
                for u, v in zip(route[:-1], route[1:]):
                    edge_data = G.get_edge_data(u, v)
                    if not edge_data:
                        print(f"  -> Données d'arête manquantes entre {u} et {v}")
                        continue
                    
                    # Prendre la première arête s'il y en a plusieurs
                    edge_attrs = list(edge_data.values())[0]

                    # Additionner la longueur
                    if 'length' in edge_attrs:
                        route_length += edge_attrs['length']

                    # Calculer le temps de trajet
                    if 'travel_time' in edge_attrs:
                        travel_time += edge_attrs['travel_time']
                    elif 'length' in edge_attrs and 'speed_kph' in edge_attrs:
                        # Convertir vitesse km/h en m/s
                        speed_ms = edge_attrs['speed_kph'] * 1000 / 3600
                        if speed_ms > 0:
                            travel_time += edge_attrs['length'] / speed_ms
                    elif 'length' in edge_attrs:
                        # Vitesse par défaut: 50 km/h
                        speed_ms = 50 * 1000 / 3600
                        travel_time += edge_attrs['length'] / speed_ms

                    # Collecter la géométrie
                    if 'geometry' in edge_attrs and edge_attrs['geometry'] is not None:
                        # Utiliser la géométrie détaillée de l'arête
                        coords = list(edge_attrs['geometry'].coords)
                        route_geometry.extend(coords)
                    else:
                        # Utiliser les coordonnées des nœuds
                        if len(route_geometry) == 0:  # Premier segment
                            x1, y1 = G.nodes[u]['x'], G.nodes[u]['y']
                            route_geometry.append((x1, y1))
                        
                        x2, y2 = G.nodes[v]['x'], G.nodes[v]['y']
                        route_geometry.append((x2, y2))

                # Vérifier que nous avons des données valides
                if route_length == 0 or len(route_geometry) < 2:
                    print(f"  -> Route invalide: longueur={route_length}, points géométrie={len(route_geometry)}")
                    continue

                # Convertir la géométrie de (lng, lat) à [lat, lng] pour Leaflet
                geometry_leaflet = [[y, x] for x, y in route_geometry]
                
                route_data = {
                    "geometry": geometry_leaflet,
                    "length": round(route_length),
                    "travel_time": round(travel_time / 60, 1)  # Convertir en minutes
                }
                
                all_routes.append(route_data)
                successful_routes += 1
                
                print(f"  -> Route {successful_routes} ajoutée: {route_data['length']}m, {route_data['travel_time']}min")

            except nx.NetworkXNoPath:
                print(f"  -> Aucun chemin réseau trouvé vers le nœud {dest}")
                continue
            except Exception as e:
                print(f"  -> Erreur de calcul vers le nœud {dest}: {e}")
                continue

        if not all_routes:
            raise ValueError("Aucun itinéraire valide n'a pu être calculé. Vérifiez que les points sont accessibles par le réseau routier.")

        # Trier les routes par temps de trajet (meilleur en premier)
        all_routes.sort(key=lambda x: x['travel_time'])
        
        print(f"Calcul terminé: {len(all_routes)} route(s) valide(s) sur {k} tentatives")
        return all_routes

    except Exception as e:
        print(f"Erreur dans calculate_route: {e}")
        traceback.print_exc()
        raise ValueError(f"Erreur dans calculate_route: {e}")


# Fonction auxiliaire pour valider une route
def validate_route_data(route_data):
    """Valide qu'une route contient toutes les données nécessaires"""
    required_fields = ['geometry', 'length', 'travel_time']
    
    for field in required_fields:
        if field not in route_data:
            return False, f"Champ manquant: {field}"
    
    if not isinstance(route_data['geometry'], list) or len(route_data['geometry']) < 2:
        return False, "Géométrie invalide: doit être une liste d'au moins 2 points"
    
    if route_data['length'] <= 0:
        return False, "Longueur invalide: doit être positive"
    
    if route_data['travel_time'] <= 0:
        return False, "Temps de trajet invalide: doit être positif"
        
    return True, "Route valide"

# def calculate_route(G, lat1, lng1, lat2, lng2):
#     """
#     Calcule le chemin le plus court entre deux coordonnées.
#     Retourne la géométrie, la longueur et le temps de trajet estimé.
#     """
#     try:
#         # Recherche des nœuds les plus proches en gérant les différentes versions d'OSMnx
#         try:
#             # Version plus récente d'OSMnx
#             orig = ox.nearest_nodes(G, lng1, lat1)
#             dest = ox.nearest_nodes(G, lng2, lat2)
#         except AttributeError:
#             try:
#                 # Version intermédiaire d'OSMnx
#                 orig = ox.distance.nearest_nodes(G, X=lng1, Y=lat1)
#                 dest = ox.distance.nearest_nodes(G, X=lng2, Y=lat2)
#             except AttributeError:
#                 # Version ancienne d'OSMnx
#                 orig = ox.get_nearest_node(G, (lat1, lng1))
#                 dest = ox.get_nearest_node(G, (lat2, lng2))
        
#         # Calculer le chemin le plus court
#         route = ox.routing.shortest_path(G, orig, dest, weight="travel_time")
        
#         if not route:
#             raise ValueError("Aucun chemin trouvé entre les points")
        
#         # Calculer correctement la longueur et le temps de trajet
#         route_length = 0
#         travel_time = 0
        
#         # Extraire la géométrie du trajet
#         # Utiliser la méthode correcte pour obtenir les attributs des arêtes
#         route_edges = []
#         for u, v in zip(route[:-1], route[1:]):
#             # Obtenir les données de l'arête entre les nœuds u et v
#             # Le dernier élément True est pour récupérer les données du premier edge si plusieurs existent
#             edge_data = G.get_edge_data(u, v, default=None)
            
#             # Il peut y avoir plusieurs arêtes entre les mêmes nœuds, nous prenons le premier
#             if edge_data is None:
#                 continue
                
#             if len(edge_data) > 0:
#                 # S'il y a plusieurs arêtes parallèles, prenez la première
#                 key = list(edge_data.keys())[0]
#                 edge_attrs = edge_data[key].copy()
#                 edge_attrs['u'] = u
#                 edge_attrs['v'] = v
#                 route_edges.append(edge_attrs)
        
#         # Parcourir tous les segments du trajet
#         route_geometry = []
#         for edge in route_edges:
#             # Additionner la longueur de chaque segment
#             if 'length' in edge:
#                 route_length += edge['length']
#             elif 'weight' in edge and edge.get('highway') is not None:
#                 # Estimation de la longueur par le poids si c'est une route
#                 route_length += edge['weight'] * 100  # Estimation grossière
            
#             # Additionner le temps de trajet de chaque segment
#             if 'travel_time' in edge:
#                 travel_time += edge['travel_time']
#             elif 'length' in edge and 'speed_kph' in edge:
#                 # Calcul du temps à partir de la distance et de la vitesse
#                 # Convertir km/h en m/s: speed_kph * 1000 / 3600
#                 speed_ms = edge['speed_kph'] * 1000 / 3600
#                 travel_time += edge['length'] / speed_ms if speed_ms > 0 else 0
#             elif 'length' in edge:
#                 # Estimation basée sur une vitesse moyenne de 50 km/h
#                 speed_ms = 50 * 1000 / 3600  # 50 km/h en m/s
#                 travel_time += edge['length'] / speed_ms
            
#             # Collecter la géométrie
#             if 'geometry' in edge:
#                 coords = list(edge['geometry'].coords)
#                 for coord in coords:
#                     route_geometry.append(coord)
#             else:
#                 # Si pas de géométrie, utiliser les coordonnées des nœuds
#                 u, v = edge['u'], edge['v']
#                 # Éviter les doublons en n'ajoutant que le nœud de départ pour chaque segment
#                 # (sauf pour le premier segment où on ajoute les deux)
#                 start_node = G.nodes[u]
#                 end_node = G.nodes[v]
                
#                 if len(route_geometry) == 0:  # Premier segment
#                     if 'x' in start_node and 'y' in start_node:
#                         route_geometry.append((start_node['x'], start_node['y']))
                
#                 # Toujours ajouter le nœud de fin
#                 if 'x' in end_node and 'y' in end_node:
#                     route_geometry.append((end_node['x'], end_node['y']))
        
#         # Arrondir la longueur en mètres
#         route_length = round(route_length)
        
#         # Convertir le temps de trajet en minutes
#         travel_time_minutes = round(travel_time / 60, 1)
        
#         return route_geometry, route_length, travel_time_minutes

#     except nx.NetworkXNoPath:
#         raise ValueError("Aucun chemin n'existe entre ces deux points")
#     except Exception as e:
#         raise ValueError(f"Erreur lors du calcul de l'itinéraire: {str(e)}")

def get_network_edges(G):
    """
    Extrait les coordonnées des arêtes du réseau pour l'affichage sur la carte.
    Renvoie une liste d'objets avec coordonnées et identifiants des nœuds.
    """
    edges = []
    for u, v, data in G.edges(data=True):
        if "geometry" in data:
            coords = list(data["geometry"].coords)
            edge_coords = [[y, x] for x, y in coords]
        else:
            start = G.nodes[u]
            end = G.nodes[v]
            if 'y' in start and 'x' in start and 'y' in end and 'x' in end:
                edge_coords = [[start['y'], start['x']], [end['y'], end['x']]]
            else:
                continue  # Skip if coords are missing

        edges.append({
            "coords": edge_coords,
            "u": u,
            "v": v
        })

    return edges
