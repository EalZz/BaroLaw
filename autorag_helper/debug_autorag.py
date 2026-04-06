import os
from autorag.evaluator import Evaluator

project_dir = '/home/ksj/BaroLaw/autorag_eval'
qa_path = os.path.join(project_dir, 'autorag_data/qa.parquet')
corpus_path = os.path.join(project_dir, 'autorag_data/corpus.parquet')
config_path = os.path.join(project_dir, 'minimal_test.yaml')

print("Initializing Evaluator...")
try:
    evaluator = Evaluator(qa_data_path=qa_path, corpus_data_path=corpus_path, project_dir=project_dir)
    print("Starting Start Trial...")
    evaluator.start_trial(config_path)
    print("Trial Finished Successfully!")
except Exception as e:
    print(f"\n[CRASH] Trial failed with error: {e}")
    import traceback
    traceback.print_exc()
