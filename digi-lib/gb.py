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
import subprocess
import json
import sys
import inspect
import time
import urllib
#import requests # --  imported from retry (with retry wrapper)
#from PIL import Image

import binascii

sys.path.append('./utils')
sys.path.append('../utils')
import keys, redis_py
from retry import retry, requests



log = open('/data/project/bub/public_html/BUB/bot/gb.log', 'a')
key = keys.google_books_key1 

def asciirepl(match):
  # replace the hexadecimal characters with ascii characters
  s = match.group()  
  return binascii.unhexlify(s[2:])  

def reformat_content(data):
  p = re.compile(r'\\x(\w{2})')
  return p.sub(asciirepl, data)


def get_id_from_string(s):
    """Return book ID from a string (can be a book code or URL)."""
    if "/" not in s:
        return s
    url = s
    match = re.search("[?&]?id=([^#&]+)", url)
    if not match:
        return None
    return match.group(1)
    
@retry(delay = 2)
def verify_id(Id_string):
    """Verify the Id and accessViewStatus(public-domain) for the book"""
    Id = get_id_from_string(Id_string)
    if Id == None:
        return 1
    try:
        r = requests.get('https://www.googleapis.com/books/v1/volumes/%s?fields=accessInfo%%2Fviewability&key=%s' %(Id, key), headers={'referer': "tools.wmflabs.org/bub"} )
    except:
        return 1
    if r.status_code == 404:
	return 1
    if r.status_code == 403:     #when GB Daily Quota(1000 requests) finished
        return 7
    if r.status_code != 200:
        return 10
    else:
        book_info = r.json()
        if book_info['accessInfo']['viewability'] != "ALL_PAGES":
            return 2
        else:
            return 0

#@retry(delay = 2)
def metadata(Id):
    """Return book information and meta-data"""
    Id = get_id_from_string(Id)
    url = 'https://www.googleapis.com/books/v1/volumes/%s?key=%s' %(Id, key)
    r = requests.get(url, headers={'referer': "tools.wmflabs.org/bub"} )
    if r.status_code == 404:
        return 1
    if r.status_code == 403:
        return 7
    if r.status_code != 200:
        return 10
    book_info = r.json()
    if book_info['accessInfo']['viewability'] != "ALL_PAGES":
        return 2
    keys1 = book_info['volumeInfo'].keys()
    return dict(
        image_url = book_info['volumeInfo']['imageLinks']['small'] if 'small' in book_info['volumeInfo']['imageLinks'].keys() else "",
        thumbnail_url = book_info['volumeInfo']['imageLinks']['thumbnail'] if 'thumbnail' in book_info['volumeInfo']['imageLinks'].keys() else "",
        printType = book_info['volumeInfo']['printType'] if 'printType' in book_info['volumeInfo'].keys() else "",
        title = book_info['volumeInfo']['title'] if 'title' in keys1 else "",
        subtitle = book_info['volumeInfo']['subtitle'] if 'subtitle' in keys1 else "",
        author = book_info['volumeInfo']['authors'][0] if 'authors' in keys1 else "",
        publisher = book_info['volumeInfo']['publisher'] if 'publisher' in keys1 else "",
        publishedDate = book_info['volumeInfo']['publishedDate'] if 'publishedDate' in keys1 else "",
        description = re.sub('<[^<]+?>', '', book_info['volumeInfo']['description']) if 'description' in keys1 else "",
        infoLink = book_info['volumeInfo']['infoLink'] if 'infoLink' in keys1 else "",
        publicDomain = book_info['accessInfo']['publicDomain'] if 'publicDomain' in book_info['accessInfo'].keys() else "",
        language = book_info['volumeInfo']['language'] if 'language' in book_info['volumeInfo'].keys() else "",
        scanner = "google",
        sponser = "Google"   
    )            
            
def get_image_url_from_page(html):
    """Get image url from page html."""
    match = re.search("preloadImg.src = '([^']*?)'", html)
    return match.group(1) 

"""
def verify_image(output_file):
    v_image = Image.open(output_file)
    v_image.verify() 
"""

@retry(delay = 2, logger = log, backoff = 2, tries = 4)
def download_image_to_file(image_url, output_file):
    """Download image from url"""  
    image_url = reformat_content(image_url)
    r = requests.get(image_url, stream=True, verify=False)
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
	#verify_image(output_file)
        

def add_serial_number_to_name(output_file, sno):
    """Convert the name to the form 001, 002..010, 011"""
    sno = str(sno)
    zeros_padding = 6-len(sno)
    output_file = output_file + "0"*zeros_padding + sno + "."
    return output_file      


def store_output_file_name(Id, output_file):
    """Save output file name to redis-memory"""
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = redis_key3+":gb:%s" %Id
    output_file_key = book_key + ":output_file"
    redis.set(output_file_key, output_file)

#@retry(logger = log, delay = 2, backoff = 2, tries = 5) 
def download_book(Id):  
    """Download book images from GB and tar them to one file"""   
    s = requests.Session()
    Id = get_id_from_string(Id)
    cover_url = "http://books.google.com/books?id=%s&hl=en&printsec=frontcover" % Id
    cover_html = s.get(cover_url, verify=False).text
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
        image_url = re.sub('w=\d+','w=2500',image_url)
	#image_url = re.sub('w\\\\x\d+','w=2500' ,image_url)
        image_url = re.sub('w\\\\x3d\d+','w\\x3d2500' ,image_url)
        output_file =  add_serial_number_to_name("/data/scratch/BUB_downloads/gb_%s_" %Id, page_no+1)
        download_image_to_file(image_url, output_file)
    final_output_file = "/data/scratch/BUB_downloads/bub_gb_%s_images.tar" %Id
    command = "tar -cf %s --directory=/data/scratch/BUB_downloads/ $(ls /data/scratch/BUB_downloads/gb_%s_*| xargs -n1 basename)" %(final_output_file, Id)
    status = subprocess.check_call(command, shell=True)
    store_output_file_name(Id, final_output_file)
    if status == 0:
        command = "rm /data/scratch/BUB_downloads/gb_%s_*" %(Id)
        status = subprocess.check_call(command, shell=True)
    return 0
    
