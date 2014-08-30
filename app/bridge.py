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

sys.path.append('../lib')
from validate_email import validate_email 

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
            
            
def commons_name_check(commonsName):
    """Check whether name available on commons"""
    try:
        r = requests.get('https://commons.wikimedia.org/w/api.php?format=json&action=query&titles=File:%s.djvu' %commonsName)
        if r.text[-15:-8] == 'missing':
            return True
        else:
            return False
    except:
        #logging.error("error %s" %commonsName)
        return False

def book_info(library_id, book_Id):
    """return metadata associated to book_id and library_id.
    Calls lib_imported.metadata()"""
    lib_module_name = str(lib_module(library_id)[0])
    if lib_module_name is not 'None':
        lib_imported = importlib.import_module(lib_module_name) 
    else:
        return None   
    return lib_imported.metadata(book_Id)
        

def download_book(library, Id):
    lib_module_name = str(lib_module(library)[0])
    if lib_module_name is not 'None':
        lib_imported = importlib.import_module(lib_module_name) 
    else:
        return None   
    return lib_imported.download_book(Id)   

        
class fields(object):
    """Verfiy the input fields (Return error codes-
    0: No error,
    3: commonsName invalid,
    4: library invalid,
    5: email invalid )"""
    def __init__(self, library_id, Id, commonsName = None, email = None):    
        self.library_id = library_id
        library_id_and_name = lib_module(self.library_id)
        self.lib_module_name = str(library_id_and_name[0])
        self.lib_name = str(library_id_and_name[1])
        if self.lib_module_name is not 'None':
            self.lib_imported = importlib.import_module(self.lib_module_name)
        Id_raw = self.lib_imported.get_id_from_string(Id) 
        self.Id = Id_raw if Id_raw is not None else Id
        self.commonsName = commonsName
        self.email = email    

    def verify_fields(self):       
        if self.lib_module_name == 'None':
            return 4
        else:
            commons_name_status = commons_name_check(self.commonsName)
            if commons_name_status != True:
                return 3
            else:
                id_status = self.lib_imported.verify_id(self.Id)
                if id_status != 0:
                    return id_status
                else:
                    if validate_email(self.email) != True:
                        return 5
                    else:
                        return 0
                        
            
            
            
