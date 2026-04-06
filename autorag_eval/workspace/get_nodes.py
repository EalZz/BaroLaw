import autorag.nodes as nodes
print("Supported Node Types:")
for key in nodes.get_node_dictionary().keys():
    print(f"- {key}")
