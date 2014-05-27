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


import requests
import re

BOOK_INFO = object


def get_id_from_string(s):
    """Return book ID from a string (can be a book code or URL)."""
    if "/" not in s:
        return s
    url = s
    match = re.search("[?&]?id=([^&]+)", url)
    if not match:
        return None
    return match.group(1)


def verify_id(ID):
    """Verify the ID and accessViewStatus(public-domain) for the book"""
    Id = get_id_from_string(ID)
    if Id == None:
        return 1
    try:
        r = requests.get('https://www.googleapis.com/books/v1/volumes/' + Id + '?projection=lite' )
    except:
        #add exception to log
        return 1
    if r.status_code == 404:
	return 1
    if r.status_code != 200:
        return 10
    else:
        global BOOK_INFO
        BOOK_INFO = r.json()
        if BOOK_INFO['accessInfo']['accessViewStatus'] == 'NONE':
            return 2
        else:
            return 0
            
            
def metadata():
    """Return book information and meta-data"""
    keys1 = BOOK_INFO['volumeInfo'].keys()
    return {
        'image_url' : BOOK_INFO['volumeInfo']['imageLinks']['small'] if 'small' in BOOK_INFO['volumeInfo']['imageLinks'].keys() else "",
        'title' : BOOK_INFO['volumeInfo']['title'] if 'title' in keys1 else "",
        'author' : BOOK_INFO['volumeInfo']['authors'][0] if 'authors' in keys1 else "",
        'publisher' : BOOK_INFO['volumeInfo']['publisher'] if 'publisher' in keys1 else "",
        'publishedDate' : BOOK_INFO['volumeInfo']['publishedDate'] if 'publishedDate' in keys1 else "",
        'description' : re.sub('<[^<]+?>', '', BOOK_INFO['volumeInfo']['description']) if 'description' in keys1 else "",
        'infoLink' : BOOK_INFO['volumeInfo']['infoLink'] if 'infoLink' in keys1 else "",
        'accessViewStatus' : BOOK_INFO['accessInfo']['accessViewStatus']  if 'accessViewStatus' in BOOK_INFO['accessInfo'].keys() else ""
    }
 
