# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License

"""Tests for sourcecode.py"""

import os
import sys

import pytest

from spyder.utils import sourcecode


def test_get_primary_at():
    code = 'import functools\nfunctools.partial'
    assert sourcecode.get_primary_at(code, len(code)) == 'functools.partial'


def test_get_identifiers():
    code = 'import functools\nfunctools.partial'
    assert set(sourcecode.get_identifiers(code)) == set(['import', 'functools',
                                                         'functools.partial'])


def test_split_source():
    code = 'import functools\nfunctools.partial'
    assert sourcecode.split_source(code) == ['import functools', 'functools.partial']
    code = code.replace('\n', '\r\n')
    assert sourcecode.split_source(code) == ['import functools', 'functools.partial']


def test_path_components():
    if sys.platform.startswith('linux'):
        path_components0 = ['','','documents','test','test.py']        
    else:
        path_components0 = ['c:','','documents','test','test.py']        
    path0 = os.path.join(*path_components0)
    assert sourcecode.path_components(path0) == path_components0


def test_differentiate_prefix():
    if sys.platform.startswith('linux'):
        path_components0 = ['','','documents','test','test.py']
        path_components1 = ['','','documents','projects','test','test.py']
    else:
        path_components0 = ['c:','','documents','test','test.py']
        path_components1 = ['c:','','documents','projects','test','test.py']
    diff_path0 = os.path.join(*['test'])
    diff_path1 = os.path.join(*['projects','test'])
    assert sourcecode.differentiate_prefix(
                        path_components0, path_components1) ==  diff_path0
    assert sourcecode.differentiate_prefix(
                        path_components1, path_components0) ==  diff_path1

def test_get_same_name_files():
    data = []
    class FileTest(object):
        def __init__(self, filename):
            self.filename = filename
    if sys.platform.startswith('linux'):
        fname = os.path.join(*['','','documents','test','test.py'])
        data.append(FileTest(fname))
        fname = os.path.join(*['','','documents','projects','test','test.py'])
        data.append(FileTest(fname))
        same_name_files = [['','','documents','test','test.py'],
                           ['','','documents','projects','test','test.py']]
    else:
        fname = os.path.join(*['c:','','documents','test','test.py'])
        data.append(FileTest(fname))
        fname = os.path.join(*['c:','','documents','projects','test','test.py'])
        data.append(FileTest(fname))
        same_name_files = [['c:','','documents','test','test.py'],
                           ['c:','','documents','projects','test','test.py']]
        assert sourcecode.get_same_name_files(data,'test.py') == same_name_files

def test_shortest_path():
    if sys.platform.startswith('linux'):
        files_path_list =[['','','documents','test','test.py'],
                          ['','','documents','projects','test','test.py']]
        shortest_path = os.path.join(*['','','documents','test','test.py'])
    else:
        files_path_list =[['c:','','documents','test','test.py'],
                          ['c:','','documents','projects','test','test.py']]
        shortest_path = os.path.join(*['c:','','documents','test','test.py'])
    assert sourcecode.shortest_path(files_path_list) == shortest_path

def test_get_file_title():
    data = []
    class FileTest(object):
        def __init__(self, filename):
            self.filename = filename
    if sys.platform.startswith('linux'):
        fname = os.path.join(*['','','documents','test','test.py'])
        data.append(FileTest(fname))
        fname = os.path.join(*['','','documents','projects','test','test.py'])
        data.append(FileTest(fname))
    else:
        fname = os.path.join(*['c:','','documents','test','test.py'])
        data.append(FileTest(fname))
        fname = os.path.join(*['c:','','documents','projects','test','test.py'])
        data.append(FileTest(fname))
    title0 = 'test.py - ' + os.path.join(*['test'])
    title1 = 'test.py - ' + os.path.join(*['projects','test'])
    assert sourcecode.get_file_title(data, 0) == title0
    assert sourcecode.get_file_title(data, 1) == title1

if __name__ == '__main__':
    pytest.main()

