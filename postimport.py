import importlib
import sys
from collections import defaultdict

_post_import_hooks = defaultdict(list)
print(sys.modules)
class PostImportFinder:
    def __init__(self):
        self._skip=set()
    
    def find_module(self, fullname, path = None):
        if fullname in self._skip:
            return None
        self._skip.add(fullname)
        return PostImportLoader(self)


class PostImportLoader:
    def __init__(self, finder):
        self._finder = finder
    
    def load_module(self, fullname):
        importlib.import_module(fullname)
        module = sys.modules[fullname]
        for func in _post_import_hooks[fullname]:
            func(module)
        self._finder._skip.remove(fullname)
        return module
    
def when_imported(names):
    def decorate(func):
        for fullname in names:
            print(f'Search for {fullname}')
            if fullname in sys.modules:
                print(f'importing {fullname}')
                func(sys.modules[fullname])
            else:
                _post_import_hooks[fullname].append(func)
        return func
    return decorate

def on_import():
    def decorate(func):
        for fullname in sys.modules:   
            print(f'Search for {fullname}')
            if f'spyder' in fullname and fullname not in sys.builtin_module_names:
                print(f'importing {fullname}')
                func(sys.modules[fullname])
            else:
                _post_import_hooks[fullname].append(func)
            return func
    return decorate
sys.meta_path.insert(0,PostImportFinder())
