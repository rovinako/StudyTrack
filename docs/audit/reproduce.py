from pathlib import Path
import importlib.util
import sys
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
from studytrack.functional import grade_summary, allocate
spec=importlib.util.spec_from_file_location('original',Path(__file__).with_name('functional_original.py'))
original=importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
for label, old, new, args in [
    ('Score above 100',original.grade_summary,grade_summary,([{'score':110,'weight':100}],)),
    ('Negative time',original.allocate,allocate,([], -1)),
    ('Duplicate task IDs',original.allocate,allocate,([{'id':1,'minutes':60},{'id':1,'minutes':60}],120))]:
    print(label)
    print('Original:',old(*args))
    try:
        print('Corrected:',new(*args))
    except ValueError as error:
        print('Corrected: rejected:',error)
