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


from BeautifulSoup import BeautifulSoup
import re
import sys
import subprocess
import unicodedata
#import requests  --  imported from retry (with retry wrapper)

sys.path.append('../utils')
sys.path.append('./utils')
import redis_py, keys
from retry import retry, requests


def normalize_to_ascii(data):
    if data == "":
        return ""
    if not isinstance(data, unicode):
        data = data.decode('utf-8') 
    return unicodedata.normalize('NFKD', data).encode('ASCII', 'ignore')


def sanitize_id_to_url(Id, action = 'sanitize'):
    """Sanitize: Change all slash '/' to underscore '_' 
    Desanitize: reverse"""
    if action == 'sanitize':
        #Id = re.sub('_', '__', Id)
        Id = re.sub('/', '_', Id)
        Id = re.sub(':', '', Id)
    elif action == 'desanitize':
        Id = re.sub('_', '/', Id)
        match = re.search('ark(.+)', Id)
	if match:
            Id = "ark:%s" % match.group(1)
    return Id


def get_id_from_string(s, action = 'sanitize'):
    """Return book ID from a string (can be a book code or URL)."""
    if len(re.findall('/',s)) < 3:
        if action == 'sanitize':
            s = sanitize_id_to_url(s)
        else:
            s= sanitize_id_to_url(s, 'desanitize')
        return s
    url = s
    match = re.search("/(ark:/[^(&/#?)]+/[^(&/#?.)]+)", url)
    if not match:
        return None
    Id = match.group(1)
    if action == 'sanitize':
        Id = sanitize_id_to_url(Id)
    else:
        Id = sanitize_id_to_url(Id, 'desanitize')
    return Id
    
       


def verify_id(Id_string): 
    """Verify the Id and public-domain status for the book"""
    Id = get_id_from_string(Id_string, 'desanitize')
    if Id == None:
        return 1
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, 'usp', Id_string)
    library_url_key = book_key + ":library_url"
    url = "http://gallica.bnf.fr/%s" %(Id)
   
    try:
        r = requests.get(url)
    except:
        return 10
    if r.status_code == 404:
	    return 1
    if r.status_code != 200:
        return 10
    else:
        source = r.text
        soup = BeautifulSoup(source)
        strong_attr = soup.findAll('strong')
        for i in strong_attr:
            public_domain = get_metadata(i, specific_tag = 'Droits')
            if not public_domain:
                continue
            if 'domaine public' in public_domain.encode('utf-8'):
                return 0               
        return 2


def extract_thumbnail_url(soup, url):
    """Exxtract and return thumbnail (from html source) url for the book"""
    u = extract_base_domain(url)
    meta_value = soup.findAll('img', attrs=dict(alt='Thumbnail'))
    if meta_value != []:
        for m in meta_value:
            if '/handle/' in m.get('src'):
                return u + m.get('src')
        return ""
    else:
        return ""
        
def get_metadata(raw_attribute, metadata = None, specific_tag = None):
    tags = ('Titre', 'Auteur', 'Éditeur', 'Date', 'Langue', 'Droits', 'Source')
    for index, tag in enumerate(tags):
        if specific_tag != None:
            if specific_tag in raw_attribute.text.encode('utf-8'):
                parent_attribute = raw_attribute.parent
                return parent_attribute.contents[2]
            else:
                continue
        if not raw_attribute.text:
            continue
        if tag in raw_attribute.text.encode('utf-8'):
            parent_attribute = raw_attribute.parent
            metadata[index] = unicode(parent_attribute.contents[2]) if len(parent_attribute.contents) >= 3 else ""
            return 0
            
            
def metadata(Id):
    """Return book information and meta-data"""
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, 'usp', Id)
    Id_raw = get_id_from_string(Id, action = 'desanitize')
    library_url_key = book_key + ":library_url"
    url = "http://gallica.bnf.fr/%s" %(Id_raw)   
    try:
        r = requests.get(url)
    except:
        return 1
    if r.status_code == 404:
	    return 1
    if r.status_code != 200:
        return 10
    else:
        source = r.text
        soup = BeautifulSoup(source)
    thumbnail_url = 'http://gallica.bnf.fr/%s/f0.highres' %Id_raw       
    strong_attr = soup.findAll('strong')
    metadata_dict = dict()
    for i in strong_attr:
        get_metadata(i, metadata_dict)
    return dict(
        image_url = thumbnail_url,
        thumbnail_url = thumbnail_url,
        printType = "BOOK",
        title = metadata_dict[0] if metadata_dict[0] else "",
        subtitle = "",
        author = metadata_dict[1] if metadata_dict[1] else "",
        publisher = metadata_dict[2] if metadata_dict[2] else "",
        publishedDate = metadata_dict[3] if metadata_dict[3] else "",
        description = "",
        infoLink = url,
        publicDomain = True,
        language = normalize_to_ascii(metadata_dict[4].strip()),
        scanner = "Gallica",
        sponser = "Gallica"
    )



from PIL import Image


def verify_image(output_file):
    v_image = Image.open(output_file)
    v_image.verify()    


@retry(delay = 2)
def download_image_to_file(image_url, output_file):
    """Download image from url"""    
    r = requests.get(image_url, stream=True)
    if r.status_code == 200:
        image_type = r.headers['content-type']
        if 'image/jpeg' in image_type:
            image_ext = 'jpeg'
        else:
          if 'image/png' in image_type:
              image_ext = 'png'
        output_file += image_ext        
        with open(output_file, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
        verify_image(output_file)
        

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
    book_key = redis_key3+":gal:%s" %Id
    output_file_key = book_key + ":output_file"
    redis.set(output_file_key, output_file)
        
   
def download_book(Id):  
    """Download book images and tar them to one file"""   
    Id = get_id_from_string(Id)
    Id_raw = get_id_from_string(Id, action = 'desanitize')
    total_pages = extract_total_pages(Id_raw)
    start_page_no = 0
    s = requests.Session()
    for page_no in range(0, total_pages+1):
        image_url = "http://gallica.bnf.fr/%s/f%s.highres" %(Id_raw, start_page_no + page_no)
        output_file =  add_serial_number_to_name("./downloads/gal_%s_" %Id, page_no)
        status = download_image_to_file(image_url, output_file)
	if status == 1:
	    return 1
    final_output_file = "./downloads/bub_gal_%s_images.tar" %Id
    command = "tar -cf %s --directory=./downloads $(ls ./downloads/gal_%s_*| xargs -n1 basename)" %(final_output_file, Id)
    status = subprocess.check_call(command, shell=True)
    store_output_file_name(Id, final_output_file)
    if status == 0:
        command = "rm ./downloads/gal_%s_*" %(Id)
        status = subprocess.check_call(command, shell=True)
    return 0

 
def extract_total_pages(Id_raw):
    r = requests.get('http://gallica.bnf.fr/%s' %Id_raw)
    soup = BeautifulSoup(r.text)
    data = soup.findAll('input', attrs={'id' : "size", 'name' : "size"})
    if data == []:
        return None
    return int(data[0].get('value'))        
 
