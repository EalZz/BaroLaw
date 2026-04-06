try:
    from autorag.support import get_support_nodes
    print(f"Supported Nodes: {list(get_support_nodes().keys())}")
except Exception as e:
    print(f"Error: {e}")
