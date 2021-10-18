import os
import importlib
import pathlib
from tools.Aspect import ModuleAspectizer


path = os.getcwd()
dir_list = os.listdir(path)
print(dir_list)
aspect = ModuleAspectizer()
print('new')

exceptions = ['pyplot.py', 'setup.py', 'bootstrap.py', 'instrument.py',
             'windows.py','pybloom.py', 'switcher.py','mainwindow.py']
def load_and_instrument(item):
     pass

for root, dirs, files in os.walk('spyder'):
    print(files)
    if 'tests' in dirs:
      dirs.remove('tests')
    if 'config' in dirs:
      dirs.remove('config')
    for f in files:
        if (f not in exceptions 
            and '_' not in f
            #and 'py' in f
            and f[-3:]=='.py'):
         print(f)
         filename = os.path.basename(f)[:-3]
         filedir = os.path.join(root,f)
         spec = importlib.util.spec_from_file_location(
                                                     filename, 
                                                     filedir)
         spec.__name__
         module = importlib.util.module_from_spec(spec)
         spec.loader.exec_module(module)
        #print(module)
         aspect.add_module(module)

aspect.instrumentize()
import bootstrap