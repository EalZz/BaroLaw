import os
import sys

# Add virtualenv's site-packages to sys.path
venv_path = os.path.expanduser("~/BaroLaw/autorag_eval/venv/lib/python3.12/site-packages")
if venv_path not in sys.path:
    sys.path.insert(0, venv_path)

try:
    from autorag.support import get_support_nodes
    print("Found get_support_nodes")
except ImportError:
    print("Could not import get_support_nodes from autorag.support")
    sys.exit(1)

# Since get_support_nodes takes a node_name, and it fails with KeyError if not found,
# we can infer it's trying to find the key in a dictionary inside.
# Let's try to find which node names are actually in there.

# Actually, the error message from the previous cat showed it's a fixed dictionary.
# Let's try some common ones.
node_list = [
    "retrieval", "lexical_retrieval", "semantic_retrieval", "hybrid_retrieval",
    "passage_reranker", "query_expansion", "passage_compressor", "passage_filter",
    "prompt_maker", "generator"
]

print("Checking Node Types:")
for node in node_list:
    try:
        get_support_nodes(node)
        print(f"- {node}: OK")
    except KeyError:
        print(f"- {node}: Not Supported")
    except Exception as e:
        print(f"- {node}: Error ({e})")
