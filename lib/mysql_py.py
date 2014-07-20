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


import MySQLdb

import keys

    
class Db(object):
    def __init__(self):
        db_host = keys.db_host
        db_username = keys.db_username
        db_password = keys.db_password
        db_database = keys.db_database
        self.database = MySQLdb.connect(db_host, db_username, db_password, db_database, use_unicode=True, charset="utf8");
        self.cursor = self.database.cursor()
        
    def execute(self, command, *args):
        """Execute MySQL command, return result if required."""
        try:    
            self.cursor.execute(command % args)
            if command[:6] != 'SELECT':
                self.database.commit()
            else: 
                data = self.cursor.fetchone()
		return data
        except: 
            if self.database:
                status = self.database.rollback()
                return status    
            
    def close(self):
        """Close the database"""
        if self.database:    
            self.database.close()        
    
            
            
