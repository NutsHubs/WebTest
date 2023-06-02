import os
import sys
import django
from pathlib import Path
from django.template.defaulttags import register

from pyvis.network import Network
import networkx as nx

NODES = {'AFTN': [], 'AMHS': [], 'OTHER': []}
START_NODES = []
END_NODES = {'AFTN': [], 'AMHS': []}
EDGES = {'PRIMARY': [], 'BACKUP': []}


def get_graph(query, source_centers: list):
    START_NODES.extend(source_centers)
    nodes_tmp = {'AFTN': set(), 'AMHS': set()}
    nodes_tmp['AFTN'] = set(source_centers)
    
    while nodes_tmp['AFTN'] or nodes_tmp['AMHS']:
        if nodes_tmp['AFTN']:
            center = nodes_tmp['AFTN'].pop()
            type = 'AFTN'
        else:
            center = nodes_tmp['AMHS'].pop()
            type = 'AMHS'
        
        if center in NODES[type]:
            continue
        
        query_str = str(query).upper()
        while(True):

            if query_str:
                result_request = request_route(center.upper(), type, query_str)
            else:
                break
            
            if not result_request is False:
                NODES[type].append(center)
                if result_request['AFTN']:
                    nodes_tmp['AFTN'].update(result_request['AFTN'])
                if result_request['AMHS']:
                    nodes_tmp['AMHS'].update(result_request['AMHS'])
                if not result_request['AFTN'] and not result_request['AMHS']:
                    END_NODES[type].append(center) 
                break
            else:
                query_str = query_str[:-1]

def request_route(center, type, aftn):
    from routes import models
    center_mod = models.Center
    aftn_mod = models.Aftn
    amhs_mod = models.Amhs
    center_ref = None 

    if center_mod.objects.filter(center=center).exists():
        center_ref = center_mod.objects.get(center=center)

    if type == 'AFTN':
        aftn_query_exists = aftn_mod.objects.filter(center=center_ref, aftn=aftn)
    else:
        aftn_query_exists = amhs_mod.objects.filter(center=center_ref, aftn=aftn)
    
    if not aftn_query_exists:
        if not center_ref:
            other_node = f'{center} {type}'
            if not other_node in NODES['OTHER']:
                NODES['OTHER'].append(f'{center} {type}')
        return False
    
    routes_tmp = {'AFTN': set(), 'AMHS': set()}
    route = aftn_query_exists.values().get()['route']
    route_res = aftn_query_exists.values().get()['route_res']

    if route:
        route = replace(route, center, type)
        routes_tmp[route[1]].add(route[0])
        EDGES['PRIMARY'].append((f'{center} {type}', f'{route[0]} {route[1]}'))
    if route_res:
        route_res = replace(route_res, center, type)
        routes_tmp[route_res[1]].add(route_res[0])
        EDGES['BACKUP'].append((f'{center} {type}', f'{route_res[0]} {route_res[1]}'))
    if type == 'AMHS':
        route_mtcu = aftn_query_exists.values().get()['route_mtcu']
        route_res_mtcu = aftn_query_exists.values().get()['route_res_mtcu']
        if route_mtcu:
            route_mtcu = f'{center} AFTN'
            routes_tmp['AFTN'].add(center)
            EDGES['PRIMARY'].append((f'{center} {type}', route_mtcu))
        if route_res_mtcu:
            route_res_mtcu = f'{center} AFTN'
            routes_tmp['AFTN'].add(center)
            EDGES['BACKUP'].append((f'{center} {type}', route_res_mtcu))

    print(f'For {center} and {type}:')
    print(routes_tmp)

    return routes_tmp
    

def replace(route, center, type):
    if 'ШЛЮЗ' in route:
        result = [center, 'AMHS']
    elif not route:
        return ['', '']
    else:
        result = [route, type]
    return result

def test():
    nx_graph = nx.MultiDiGraph()

    aftn_nodes = []
    amhs_nodes = []
    other_nodes = []
    s_nodes = []
    e_aftn_nodes = []
    e_amhs_nodes = []

    for aftn in NODES['AFTN']:
        if aftn in START_NODES:
            s_nodes.append(f'{aftn}\nAFTN')
        else:
            if aftn in END_NODES['AFTN']:
                e_aftn_nodes.append(f'{aftn}\nAFTN')
            else:
                aftn_nodes.append(f'{aftn}\nAFTN')
    for amhs in NODES['AMHS']:
        if amhs in END_NODES['AMHS']:
            e_amhs_nodes.append(f'{amhs}\nAMHS')
        else:
            amhs_nodes.append(f'{amhs}\nAMHS')
    for other in NODES['OTHER']:
        other_nodes.append(other.replace(' ', '\n'))
    p_edges = []
    b_edges = []
    for edge in EDGES['PRIMARY']:
        p_edges.append((str(edge[0]).replace(' ', '\n'), str(edge[1]).replace(' ', '\n')))
    for edge in EDGES['BACKUP']:
        b_edges.append((str(edge[0]).replace(' ', '\n'), str(edge[1]).replace(' ', '\n')))
    
    nx_graph.add_nodes_from(s_nodes, shape='box', color='yellow')

    nx_graph.add_nodes_from(aftn_nodes, shape='box')
    nx_graph.add_nodes_from(e_aftn_nodes, shape='box', color='red')

    nx_graph.add_nodes_from(amhs_nodes, shape='circle')
    nx_graph.add_nodes_from(e_amhs_nodes, shape='circle', color='red')

    nx_graph.add_nodes_from(other_nodes, shape='circle', color='red')

    nx_graph.add_edges_from(p_edges, color='black')
    nx_graph.add_edges_from(b_edges, color='red')

    nt = Network('1500px', '1800px', notebook=True, directed=True)
    # populates the nodes and edges data structures
    nt.from_nx(nx_graph)
    nt.set_edge_smooth('dynamic')
    
    nt.set_options(
        """
        const options = {
            "physics": {
                "forceAtlas2Based": {
                "gravitationalConstant": -409,
                "centralGravity": 0.195,
                "springLength": 150,
                "springConstant": 0.235
                },
                "minVelocity": 1,
                "solver": "forceAtlas2Based"
            }
        }
        """
    )
    
    #nt.show_buttons(filter_=["physics"])
    #nt.toggle_physics(False)

    #nt.barnes_hut()
    nt.show('nx.html')


if __name__ == '__main__':
    sys.path.append(f'{Path(__file__).resolve().parent.parent}/')
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
    from django.conf import settings

    if not settings.configured:
        django.setup()
    get_graph('he', ['UIII', 'UWWW', 'UEEE', 'ULLL', 'UNKL', 'UNNT', 'URRR', 'USSV', 'USTU', 'UUUU', 'UUYY', 'UHMM', 'UHPP', 'UHHH'])
    #get_graph('uu', ['ULLL'])
    #get_graph('ee', ['ULLL'])
    test()
    print(EDGES)
    print(NODES)