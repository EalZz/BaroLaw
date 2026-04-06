import autorag
from autorag import node_dictionary
print("AutoRAG Node Dictionary Keys:")
for key in sorted(node_dictionary.keys()):
    print(f"- {key}")
