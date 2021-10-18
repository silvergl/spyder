from inspect import getmembers, isfunction, isclass, getmodule
from postimport import on_import, when_imported
import os
import importlib
#import pathlib
from tools.Aspect import _class_decorator, instrument

path = os.getcwd()
dir_list = os.listdir(path)
print(dir_list)
#aspect = ModuleAspectizer()
print('new')

exceptions = ['pyplot.py', 'setup.py', 'bootstrap.py', 'instrument.py',
             'windows.py','pybloom.py', 'switcher.py','mainwindow.py','enum.py' ]
list_of_module_names = []

# collect modulenames
for root, dirs, files in os.walk('spyder'):
    print(files)
    if 'tests' in dirs:
      dirs.remove('tests')
    for f in files:
        if (f not in exceptions 
            and '_' not in f
            #and 'py' in f
            and f[-3:]=='.py'):
         print(f)
         filename = os.path.basename(f)[:-3]
         filedir = os.path.join(root,f)
         print(f'filedir: {filedir}')
         spec = importlib.util.spec_from_file_location(
                                                     filename, 
                                                     filedir)
        print(f'spec name: {spec.name}')
        list_of_module_names.append(spec.name)

@when_imported(list_of_module_names)
def decorate(mod):
    # Decorate classes
    print(f'importing {mod}')
    for name, member in getmembers(mod, isclass):
        print(f'apply decorator for: {name},{member} ')
        if(member.__module__==mod.__name__):
            print(member.__module__)
            print(mod.__name__)
            setattr(mod, name, _class_decorator(member))
        #    print('class')
      
    
    for name, member in getmembers(mod,isfunction):
        if(member.__module__==mod.__spec__.name):
            mod.__dict__[name] = instrument(member)
         #   print('func')

