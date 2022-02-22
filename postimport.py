import importlib
import sys
from collections import defaultdict
from tools.aspect import _class_decorator, instrument, decorate_members
from inspect import *

sys.meta_path.insert(0,PostImportFinder())
#def decorate_members(mod):
    # Decorate classes
    #print(f'importing {mod}')
    #for name, member in getmembers(mod, isclass):
    #    print(f'apply decorator for: {name},{member} ')
    #    if(member.__module__==mod.__name__):
    #        print(member.__module__)
    #        print(mod.__name__)
    #        setattr(mod, name, _class_decorator(member))
        #    print('class')
#    if mod.__spec__.name =='mainwindow':
#        print('skip')
#        return
    
#    for name, member in getmembers(mod,isfunction):
#        if(member.__module__==mod.__spec__.name):
#            mod.__dict__[name] = instrument(member)
         #   print('func')   

#class PostImportFinder:
#    def __init__(self):
#        self._skip=set()
    
#    def find_module(self, fullname, path = None):
#        if fullname in self._skip:
#            return None
#        self._skip.add(fullname)
#        return PostImportLoader(self)


#class PostImportLoader:
#    def __init__(self, finder):
#        self._finder = finder
    
#    def load_module(self, fullname):
#        importlib.import_module(fullname)
#        module = sys.modules[fullname]
#        if 'spyder' in fullname and 'manager' not in fullname:
#                decorate_members(module)
#        self._finder._skip.remove(fullname)
#        return module


#def when_imported(names):
#    def decorate(func):
#        for fullname in names:
#            print(f'Search for {fullname}')
#            if fullname in sys.modules:
#                print(f'importing {fullname}')
#                func(sys.modules[fullname])
#           else:
#                _post_import_hooks[fullname].append(func)
#        return func
#    return decorate

#def on_import():
#    def decorate(func):
#        for fullname in sys.modules:   
#            print(f'Search for {fullname}')
#           if f'spyder' in fullname and fullname not in sys.builtin_module_names:
#                print(f'importing {fullname}')
#                func(sys.modules[fullname])
#            else:
#                _post_import_hooks[fullname].append(func)
#            return func
#    return decorate

