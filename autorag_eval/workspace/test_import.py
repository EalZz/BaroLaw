print("Script Started")
try:
    from autorag.nodes.retrieval import bm25, vectordb
    print("Import Success: bm25, vectordb")
except Exception as e:
    import traceback
    print(f"Import Failed: {e}")
    traceback.print_exc()
print("Script Finished")
