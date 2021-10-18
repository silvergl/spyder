from monitoring.Controller import MonitoringController, WriterController

from monitoring.traceregistry import TraceRegistry
import aspectlib
import os
import importlib
from monitoring.Record import *
monitoring_controller = MonitoringController(WriterController())
trace_reg = TraceRegistry()

@aspectlib.Aspect(bind=True)
def wrapper(cutpoint, *args, **kwargs):
        print('before')
        trace = trace_reg.get_trace()
        print(trace)
        if(trace is None):
            trace = trace_reg.register_trace()
            monitoring_controller.new_monitoring_record(trace)
        
        trace_id = trace.trace_id
            
        timestamp = monitoring_controller.time_source_controller.get_time()
        func_module = cutpoint.__module__
        class_signature = cutpoint.__qualname__.split(".", 1)[0]
        monitoring_controller.new_monitoring_record(BeforeOperationEvent(
               timestamp,
               trace_id,
               trace.get_next_order_id(),
               cutpoint.__name__,
               f'{func_module}.{class_signature}'))

        try:
            result = yield aspectlib.Proceed
        except Exception as e:
            print('after failed')
            timestamp = monitoring_controller.time_source_controller.get_time()
            monitoring_controller.new_monitoring_record(
                AfterOperationFailedEvent(timestamp,
                                          -1
                                          -2, 
                                          cutpoint.__name__,
                                          f'{func_module}.{class_signature}',
                                          repr(e)))

            raise e
        print('after')
        timestamp = monitoring_controller.time_source_controller.get_time()
        monitoring_controller.new_monitoring_record(AfterOperationEvent(
            timestamp,
            trace_id,
            trace.get_next_order_id(),
            cutpoint.__name__,
            f'{func_module}.{class_signature}'))
        yield aspectlib.Return(result)

path = os.getcwd()
dir_list = os.listdir(path)
print(dir_list)
#aspect = ModuleAspectizer()
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
         module = importlib.util.module_from_spec(spec)
         aspectlib.weave(module, wrapper)
         #spec.loader.exec_module(module)
        #print(module)
         #aspect.add_module(module)

#aspect.instrumentize()
import bootstrap

@aspectlib.Aspect
def test():
    result = yield 
    yield aspectlib.Return(1)



