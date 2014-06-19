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
import json
import subprocess


def get_id_from_string(s):
    """Return book ID from a string (can be a book code or URL)."""
    if "/" not in s:
        return s
    url = s
    match = re.search("[?&]?id=([^&]+)", url)
    if not match:
        return None
    return match.group(1)
    

def verify_id(Id_string):
    """Verify the Id and accessViewStatus(public-domain) for the book"""
    Id = get_id_from_string(Id_string)
    if Id == None:
        return 1
    try:
        r = requests.get('https://www.googleapis.com/books/v1/volumes/%s?projection=lite' %Id )
    except:
	    #logging.error("error requests: %s" %Id)
        return 1
    if r.status_code == 404:
	return 1
    if r.status_code != 200:
        return 10
    else:
        book_info = r.json()
        if book_info['accessInfo']['accessViewStatus'] == 'NONE':
            return 2
        else:
            return 0


def metadata(Id):
    """Return book information and meta-data"""
    Id = get_id_from_string(Id)
    r = requests.get('https://www.googleapis.com/books/v1/volumes/%s' %Id )
    book_info = r.json()
    keys1 = book_info['volumeInfo'].keys()
    return dict(
        image_url = book_info['volumeInfo']['imageLinks']['small'] if 'small' in book_info['volumeInfo']['imageLinks'].keys() else "",
        printType = book_info['volumeInfo']['printType'] if 'printType' in book_info['volumeInfo'].keys() else "",
        title = book_info['volumeInfo']['title'] if 'title' in keys1 else "",
        subtitle = book_info['volumeInfo']['subtitle'] if 'subtitle' in keys1 else "",
        author = book_info['volumeInfo']['authors'][0] if 'authors' in keys1 else "",
        publisher = book_info['volumeInfo']['publisher'] if 'publisher' in keys1 else "",
        publishedDate = book_info['volumeInfo']['publishedDate'] if 'publishedDate' in keys1 else "",
        description = re.sub('<[^<]+?>', '', book_info['volumeInfo']['description']) if 'description' in keys1 else "",
        infoLink = book_info['volumeInfo']['infoLink'] if 'infoLink' in keys1 else "",
        accessViewStatus = book_info['accessInfo']['accessViewStatus']  if 'accessViewStatus' in book_info['accessInfo'].keys() else "",
        language = book_info['volumeInfo']['language'] if 'language' in book_info['volumeInfo'].keys() else ""    
    )
            
            
def get_image_url_from_page(html):
    """Get image url from page html."""
    match = re.search(r"preloadImg.src = '([^']*?)'", html)
    return match.group(1) 

    
def download_image_to_file(image_url, output_file):
    """Download image from url"""    
    r = requests.get(image_url, stream=True)
    if r.status_code == 200:
        image_type = r.headers['content-type']
        if image_type == 'image/jpeg':
            image_ext = 'jpeg'
        else:
          if image_type == 'image/png':
              image_ext = 'png'
        output_file += image_ext        
        with open(output_file, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
	#logging.info("Downloaded %s" %(output_file))
        
   
def download_book(Id):  
    """Download book images from GB and convert them to one pdf
    downloads path- bot/downloads/<LIBRARY-ID>_<BOOK-ID>.pdf"""   
    s = requests.Session()
    cover_url = "http://books.google.com/books?id=%s&hl=en&printsec=frontcover" % Id
    cover_html = s.get(cover_url).text
    match = re.search(r'_OC_Run\((.*?)\);', cover_html)
    oc_run_args = json.loads("[%s]" %(match.group(1)))
    pages_info = oc_run_args[0]
    page_ids = [x["pid"] for x in sorted(pages_info["page"], key=lambda d: d["order"])]
    prefix = pages_info["prefix"].decode("raw_unicode_escape")
    for page_no, page_id in enumerate(page_ids):
        page_url = prefix + "&pg=" + page_id
        response = s.get(page_url)
        page_html = response.text
        image_url = get_image_url_from_page(page_html)
        output_file = "./downloads/gb_" + str(Id) + "_" + str((page_no+1)) + "."
        download_image_to_file(image_url, output_file)
    total_pages = page_no+1
    command = "for name in ./downloads/gb_%s_*; do convert $name -units PixelsPerInch -density 150x150 $(echo ${name%%.*}).pdf; done; gs -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -sOutputFile=./downloads/gb_%s.pdf $(ls -1v ./downloads/gb_%s_*.pdf);" %(Id,Id,Id)
    status = subprocess.check_call(command, shell=True)
    if status == 0:
        command = "rm ./downloads/gb_%s_*" %(Id)
        status = subprocess.check_call(command, shell=True)
    return 0
