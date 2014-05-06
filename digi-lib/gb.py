#!/usr/bin/python
# -*- coding: utf-8 -*-

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#    
# @author Rohit Dua <8ohit.dua@gmail.com>


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
        return False
    try:
        r = requests.get('https://www.googleapis.com/books/v1/volumes/' + Id + '?projection=lite' )
    except:
        #add exception to log
        return False
    if r.status_code != 200:
        return False
    else:
        global BOOK_INFO
        BOOK_INFO = r.json()
        if BOOK_INFO['accessInfo']['accessViewStatus'] == 'NONE':
            return False
        else:
            return True
            
            
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
        
