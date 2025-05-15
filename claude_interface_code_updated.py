import networkx as nx
import osmnx as ox
import os
import pickle

NETWORK_FILE = "VALLORBE_MERGE.graphml"
PICKLE_FILE = "VALLORBE_MERGE.pkl"  # Un format plus efficace pour stocker le graphe

def load_network():
    """
    Charge le réseau depuis un fichier s'il existe, sinon le crée et le sauvegarde.
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
    
    # Sinon, créer un nouveau réseau
    else:
        print("Création d'un nouveau réseau pour le canton de Vaud...")
        try:
            # Limite du réseau à une zone plus petite pour réduire la taille
            G = ox.graph.graph_from_place("Vaud, Suisse", network_type="drive")
            G = ox.routing.add_edge_speeds(G)
            G = ox.routing.add_edge_travel_times(G)
            
            # Sauvegarde aux deux formats
            ox.save_graphml(G, NETWORK_FILE)
            with open(PICKLE_FILE, 'wb') as f:
                pickle.dump(G, f)
                
            return G
        except Exception as e:
            print(f"Erreur lors de la création du réseau: {e}")
            # Solution de secours: créer un petit réseau autour de Vallorbe
            G = ox.graph.graph_from_place("Vallorbe, District du Jura-Nord vaudois, Vaud, 1337, Suisse", network_type="drive")
            G = ox.routing.add_edge_speeds(G)
            G = ox.routing.add_edge_travel_times(G)
            
            # Sauvegarde aux deux formats
            ox.save_graphml(G, NETWORK_FILE)
            with open(PICKLE_FILE, 'wb') as f:
                pickle.dump(G, f)
                
            return G

def calculate_route(G, lat1, lng1, lat2, lng2):
    """
    Calcule le chemin le plus court entre deux coordonnées.
    Retourne la géométrie, la longueur et le temps de trajet estimé.
    """
    try:
        # Recherche des nœuds les plus proches en gérant les différentes versions d'OSMnx
        try:
            # Version plus récente d'OSMnx
            orig = ox.nearest_nodes(G, lng1, lat1)
            dest = ox.nearest_nodes(G, lng2, lat2)
        except AttributeError:
            try:
                # Version intermédiaire d'OSMnx
                orig = ox.distance.nearest_nodes(G, X=lng1, Y=lat1)
                dest = ox.distance.nearest_nodes(G, X=lng2, Y=lat2)
            except AttributeError:
                # Version ancienne d'OSMnx
                orig = ox.get_nearest_node(G, (lat1, lng1))
                dest = ox.get_nearest_node(G, (lat2, lng2))
        
        # Calculer le chemin le plus court
        route = ox.routing.shortest_path(G, orig, dest, weight="travel_time")
        
        if not route:
            raise ValueError("Aucun chemin trouvé entre les points")
        
        # Calculer correctement la longueur et le temps de trajet
        route_length = 0
        travel_time = 0
        
        # Extraire la géométrie du trajet
        # Utiliser la méthode correcte pour obtenir les attributs des arêtes
        route_edges = []
        for u, v in zip(route[:-1], route[1:]):
            # Obtenir les données de l'arête entre les nœuds u et v
            # Le dernier élément True est pour récupérer les données du premier edge si plusieurs existent
            edge_data = G.get_edge_data(u, v, default=None)
            
            # Il peut y avoir plusieurs arêtes entre les mêmes nœuds, nous prenons le premier
            if edge_data is None:
                continue
                
            if len(edge_data) > 0:
                # S'il y a plusieurs arêtes parallèles, prenez la première
                key = list(edge_data.keys())[0]
                edge_attrs = edge_data[key].copy()
                edge_attrs['u'] = u
                edge_attrs['v'] = v
                route_edges.append(edge_attrs)
        
        # Parcourir tous les segments du trajet
        route_geometry = []
        for edge in route_edges:
            # Additionner la longueur de chaque segment
            if 'length' in edge:
                route_length += edge['length']
            elif 'weight' in edge and edge.get('highway') is not None:
                # Estimation de la longueur par le poids si c'est une route
                route_length += edge['weight'] * 100  # Estimation grossière
            
            # Additionner le temps de trajet de chaque segment
            if 'travel_time' in edge:
                travel_time += edge['travel_time']
            elif 'length' in edge and 'speed_kph' in edge:
                # Calcul du temps à partir de la distance et de la vitesse
                # Convertir km/h en m/s: speed_kph * 1000 / 3600
                speed_ms = edge['speed_kph'] * 1000 / 3600
                travel_time += edge['length'] / speed_ms if speed_ms > 0 else 0
            elif 'length' in edge:
                # Estimation basée sur une vitesse moyenne de 50 km/h
                speed_ms = 50 * 1000 / 3600  # 50 km/h en m/s
                travel_time += edge['length'] / speed_ms
            
            # Collecter la géométrie
            if 'geometry' in edge:
                coords = list(edge['geometry'].coords)
                for coord in coords:
                    route_geometry.append(coord)
            else:
                # Si pas de géométrie, utiliser les coordonnées des nœuds
                u, v = edge['u'], edge['v']
                # Éviter les doublons en n'ajoutant que le nœud de départ pour chaque segment
                # (sauf pour le premier segment où on ajoute les deux)
                start_node = G.nodes[u]
                end_node = G.nodes[v]
                
                if len(route_geometry) == 0:  # Premier segment
                    if 'x' in start_node and 'y' in start_node:
                        route_geometry.append((start_node['x'], start_node['y']))
                
                # Toujours ajouter le nœud de fin
                if 'x' in end_node and 'y' in end_node:
                    route_geometry.append((end_node['x'], end_node['y']))
        
        # Arrondir la longueur en mètres
        route_length = round(route_length)
        
        # Convertir le temps de trajet en minutes
        travel_time_minutes = round(travel_time / 60, 1)
        
        return route_geometry, route_length, travel_time_minutes

    except nx.NetworkXNoPath:
        raise ValueError("Aucun chemin n'existe entre ces deux points")
    except Exception as e:
        raise ValueError(f"Erreur lors du calcul de l'itinéraire: {str(e)}")

def get_network_edges(G):
    """
    Extrait les coordonnées des arêtes du réseau pour l'affichage sur la carte.
    Renvoie une liste de paires de coordonnées [lat, lng].
    """
    edges = []
    for u, v, data in G.edges(data=True):
        if "geometry" in data:
            # Si l'arête a une géométrie complexe (LineString)
            coords = list(data["geometry"].coords)
            # Convertir du format [x, y] au format [y, x] pour Leaflet
            edge_coords = [[y, x] for x, y in coords]
            edges.append(edge_coords)
        else:
            # Si l'arête est une ligne droite entre deux noeuds
            start = G.nodes[u]
            end = G.nodes[v]
            # Vérifier que les coordonnées nécessaires existent
            if 'y' in start and 'x' in start and 'y' in end and 'x' in end:
                edges.append([[start['y'], start['x']], [end['y'], end['x']]])
    
    return edges

# import networkx as nx
# import osmnx as ox
# import os
# import pickle

# NETWORK_FILE = "Vallorbe_drive.graphml"
# PICKLE_FILE = "Vallorbe_drive.pkl"  # Un format plus efficace pour stocker le graphe

# def load_network():
#     """
#     Charge le réseau depuis un fichier s'il existe, sinon le crée et le sauvegarde.
#     Utilise pickle pour un chargement plus rapide.
#     """
#     # Essayer d'abord avec pickle pour un chargement plus rapide
#     if os.path.exists(PICKLE_FILE):
#         print(f"Chargement du réseau depuis {PICKLE_FILE}")
#         with open(PICKLE_FILE, 'rb') as f:
#             G = pickle.load(f)
#         return G
    
#     # Sinon, essayer avec GraphML
#     elif os.path.exists(NETWORK_FILE):
#         print(f"Chargement du réseau depuis {NETWORK_FILE}")
#         G = ox.load_graphml(NETWORK_FILE)
#         # Sauvegarder au format pickle pour la prochaine fois
#         with open(PICKLE_FILE, 'wb') as f:
#             pickle.dump(G, f)
#         return G
    
#     # Sinon, créer un nouveau réseau
#     else:
#         print("Création d'un nouveau réseau pour le canton de Vaud...")
#         try:
#             # Limite du réseau à une zone plus petite pour réduire la taille
#             G = ox.graph.graph_from_place("Vaud, Suisse", network_type="drive")
#             G = ox.routing.add_edge_speeds(G)
#             G = ox.routing.add_edge_travel_times(G)
            
#             # Sauvegarde aux deux formats
#             ox.save_graphml(G, NETWORK_FILE)
#             with open(PICKLE_FILE, 'wb') as f:
#                 pickle.dump(G, f)
                
#             return G
#         except Exception as e:
#             print(f"Erreur lors de la création du réseau: {e}")
#             # Solution de secours: créer un petit réseau autour de Vallorbe
#             G = ox.graph.graph_from_place("Vallorbe, District du Jura-Nord vaudois, Vaud, 1337, Suisse", network_type="drive")
#             G = ox.routing.add_edge_speeds(G)
#             G = ox.routing.add_edge_travel_times(G)
            
#             # Sauvegarde aux deux formats
#             ox.save_graphml(G, NETWORK_FILE)
#             with open(PICKLE_FILE, 'wb') as f:
#                 pickle.dump(G, f)
                
#             return G

# def calculate_route(G, lat1, lng1, lat2, lng2):
#     """
#     Calcule le chemin le plus court entre deux coordonnées.
#     Retourne la géométrie, la longueur et le temps de trajet estimé.
#     """
#     try:
#         # Trouver les noeuds les plus proches des coordonnées
#         orig = ox.distance.nearest_nodes(G, X=lng1, Y=lat1)
#         dest = ox.distance.nearest_nodes(G, X=lng2, Y=lat2)
        
#         # Calculer le chemin le plus court
#         route = ox.routing.shortest_path(G, orig, dest, weight="travel_time")
        
#         if not route:
#             raise ValueError("Aucun chemin trouvé entre les points")
        
#         # Extraire la géométrie et calculer la longueur
#         route_gdf = ox.routing.route_to_gdf(G, route)
#         route_geometry = route_gdf.geometry.iloc[0].coords[:]
#         route_length = round(sum(route_gdf["length"]))
        
#         # Calculer le temps de trajet total en secondes
#         travel_time_seconds = sum(route_gdf["travel_time"])
        
#         # Convertir en minutes pour l'affichage
#         travel_time_minutes = round(travel_time_seconds / 60, 1)
        
#         return route_geometry, route_length, travel_time_minutes

#     except nx.NetworkXNoPath:
#         raise ValueError("Aucun chemin n'existe entre ces deux points")
#     except Exception as e:
#         raise ValueError(f"Erreur lors du calcul de l'itinéraire: {str(e)}")

# def get_network_edges(G):
#     """
#     Extrait les coordonnées des arêtes du réseau pour l'affichage sur la carte.
#     Renvoie une liste de paires de coordonnées [lat, lng].
#     """
#     edges = []
#     for u, v, data in G.edges(data=True):
#         if "geometry" in data:
#             # Si l'arête a une géométrie complexe (LineString)
#             coords = list(data["geometry"].coords)
#             # Convertir du format [x, y] au format [y, x] pour Leaflet
#             edge_coords = [[y, x] for x, y in coords]
#             edges.append(edge_coords)
#         else:
#             # Si l'arête est une ligne droite entre deux noeuds
#             start = G.nodes[u]
#             end = G.nodes[v]
#             # Vérifier que les coordonnées nécessaires existent
#             if 'y' in start and 'x' in start and 'y' in end and 'x' in end:
#                 edges.append([[start['y'], start['x']], [end['y'], end['x']]])
    
#     return edges