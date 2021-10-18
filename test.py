import builtins 
from inspect import getmembers, getmodule, isclass, isfunction
from tools.Aspect import _class_decorator, instrument
old_imp = builtins.__import__

def decorate(mod):
    # Decorate classes
    #for name, member in getmembers(mod, isclass):
       # print((name,member))
     #   if(member.__module__==mod.__name__):
      #      setattr(mod, name, _class_decorator(member))
        #    print('class')
      
    
    for name, member in getmembers(mod,isfunction):
        if(member.__module__==mod.__name__
        and (name,member) not in getmembers(builtins)):
            mod.__dict__[name] = instrument(member)
         #   print('func')

def add_attr(mod):
    for name, val in getmembers(mod):
        if isclass(val):
            setattr(val, 'a', 10)

def custom_import(*args, **kwargs):
    m = old_imp(*args, **kwargs)
    decorate(m)
    return m

builtins.__import__ = custom_import