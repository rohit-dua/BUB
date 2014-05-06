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

sys.path.append('../lib')
from validate_email import validate_email 

sys.path.append('../digi-lib')      #path to user-created digital-library modules(import in exec function)

LIBRARY_NAME = ""
parsed_ID = ""

def lib_module(LIBRARY):
    """Return name of the module associated with library, extracted from config"""
    global LIBRARY_NAME
    config = open('../config', 'r')
    lines = config.readlines() 
    for line in lines[1:]:
        line = re.split('\s+',line)
        if line[0] == '#end':
            config.close()
            return None
        elif line[0] == LIBRARY:
            config.close()
            LIBRARY_NAME = line[2]
            return line[1]
            
            

def verify(LIBRARY, ID, COMMONSNAME, EMAIL):
    """Verfiy the input fields (Return error codes-0,1,2,3,4)"""
    lib_module_name = str(lib_module(LIBRARY))
    if lib_module_name == 'None':
        return 4
    else:
        commons_name_status = commons_name_check(COMMONSNAME)
        if commons_name_status != True:
            return 3
        else:
            exec('import ' + lib_module_name + ' as lib_working') in globals(),globals()
            id_status = lib_working.verify_id(ID)
            if id_status != 0:
                return id_status
            else:
                if validate_email(EMAIL) != True:
                    return 5
                else:
                    global parsed_ID
                    parsed_ID = lib_working.get_id_from_string(ID)
                    return 0
        


def commons_name_check(COMMONSNAME):
    """Check whether name available on commons"""
    try:
        r = requests.get('https://commons.wikimedia.org/w/api.php?format=json&action=query&titles=File:' + COMMONSNAME + '.djvu')
        if r.text[-15:-8] == 'missing':
            return True
        else:
            return False
    except:
        #add exception to log
        return False
        

def thumbnail_info():
    return lib_working.metadata()

