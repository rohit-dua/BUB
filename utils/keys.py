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


import json
import os


basedir = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))


__settings_path = os.path.join(basedir, 'settings.json')
__json_data = open(__settings_path)
__settings = json.load(__json_data)  

    
redis_key1 = __settings['redis']['key_1']
redis_key2 = __settings['redis']['key_2']
redis_key3 = __settings['redis']['key_3']
redis_key4 = __settings['redis']['key_4']


"S3 IA API keys"
S3_access_key = __settings['ia']['S3_access_key']
S3_secret_key = __settings['ia']['S3_secret_key']


"Lock Keys"
lock_key1 = __settings['lock']['key_1']


"Library API keys"
google_books_key1 = __settings['google_books']['key_1']
google_books_key2 = __settings['google_books']['key_2']
google_books_key3 = __settings['google_books']['key_3']
google_books_key4 = __settings['google_books']['key_4']


"Local Redis server credentials"
redis_host = __settings['redis']['host']
redis_port = int(__settings['redis']['port'])


"MySQL credentials"
db_host = __settings['db']['host']
db_username = __settings['db']['username']
db_password = __settings['db']['password']
db_database = __settings['db']['database']
SQLALCHEMY_DATABASE_URI = 'mysql://%s:%s@%s/%s' %(db_username, db_password, db_host, db_database)


"Flask secret key"
flask_app_secret = __settings['flask']
admin_password = __settings['admin']


"HathiTrust Data API Keys"
hathitrust_api_access_key = __settings['hathi_trust']['access_key']
hathitrust_api_secret_key = __settings['hathi_trust']['secret_key']

