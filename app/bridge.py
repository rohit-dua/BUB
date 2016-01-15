#!/usr/bin/python
# -*- coding: utf-8 -*-

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#    
# @author Rohit Dua <8ohit.dua AT gmail DOT com>
# Hosted at http://tools.wmflabs.org/bub/
# Maintained at https://github.com/rohit-dua/BUB


import re
import sys
import requests
import importlib

from validate_email import validate_email 

sys.path.append('./digi-lib')       # used in dynamic import
sys.path.append('../digi-lib')


def lib_module(library_id):
    """Return tuple (module_name, library_name) associated to library_id extracted from config"""
    config = open('../config', 'r')
    lines = config.readlines() 
    for line in lines[1:]:
        line = re.split('\s+',line)
        if line[0] is '#end':
            config.close()
            return (None, None)
        elif line[0] == library_id:
            config.close()
            return (line[1],line[2])
            

def book_info(library_id, book_Id):
    """Return metadata associated to book_id and library_id."""
    lib_module_name = str(lib_module(library_id)[0])
    if lib_module_name is not 'None':
        lib_imported = importlib.import_module(lib_module_name) 
    else:
        return None   
    return lib_imported.metadata(book_Id)
        

def download_book(library, Id, id_for_key=None):
    """Call download method for the Id, from the specified library"""
    lib_module_name = str(lib_module(library)[0])
    if lib_module_name is not 'None':
        lib_imported = importlib.import_module(lib_module_name) 
    else:
        return None   
    if id_for_key==None:
	return_id=Id
    else:
	return_id=id_for_key
    return lib_imported.download_book(Id, return_id)   

        
class fields(object):
    """Verify the input fields (Return error codes-
    0: No error,
    4: library invalid,
    5: email invalid )"""
    def __init__(self, library_id, Id, email = ""):    
        self.library_id = library_id
        library_id_and_name = lib_module(self.library_id)
        self.lib_module_name = str(library_id_and_name[0]) if library_id_and_name != None else None
        self.lib_name = str(library_id_and_name[1]) if library_id_and_name != None else None
        self.lib_imported = importlib.import_module(self.lib_module_name) if self.lib_module_name != None else None
        Id_raw = self.lib_imported.get_id_from_string(Id) if self.lib_imported != None else None
        self.Id = Id_raw if Id_raw != None else Id
        self.email = email
        print "EMAIL:%s:"%email    

    def verify_fields(self):       
        if self.lib_module_name == None:
            return 4
        else:
            id_status = self.lib_imported.verify_id(self.Id)
            if id_status != 0:
                return id_status
            else:
                if validate_email(self.email) != True and self.email not in (None, ""):
                    return 5
                else:
                    return 0
                        
