from app.graph.client import GraphClient, get_graph


def graph_dep() -> GraphClient:
    return get_graph()
