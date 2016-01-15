#!/data/project/bub/public_html/BUB/flask/bin/python
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
    
       
def OAI_metadata_content(name, soup, burst=False):
    """Extract and return the specified meta-tags value"""
    meta_value = soup.findAll('meta', attrs=dict(name=name))
    if meta_value != []:
        if burst:
            return [m.get('content') for m in meta_value]
        else:
            return meta_value[0].get('content')
    else:
        if burst:
            return []
        else:
            return ""


           

def verify_id(Id_string): 
    """Verify the Id and public-domain status for the book"""
    Id = get_id_from_string(Id_string, 'desanitize')
    if Id == None:
        return 1
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, 'gal', Id_string)
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
        rights= OAI_metadata_content("DC.rights", soup, burst=True)
        for i in rights:
            if not rights:
                continue
            if i.strip().lower().encode('utf-8') in ('domaine public', 'public domain'):
                return 0               
        return 2


def metadata(Id):
    """Return book information and meta-data"""
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, 'usp', Id)
    Id_raw = get_id_from_string(Id, action = 'desanitize')
    Id_raw = Id_raw[:-1] if Id_raw[-1] == '/' else Id_raw
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
    thumbnail_url = 'http://gallica.bnf.fr/%s.thumbnail' %Id_raw       
    source = r.text
    soup = BeautifulSoup(source)
    return dict(
        image_url = thumbnail_url,
        thumbnail_url = thumbnail_url,
        printType = "BOOK",
        title = OAI_metadata_content("DC.title", soup),
        subtitle = "",
        author = OAI_metadata_content("DC.creator", soup),
        publisher = OAI_metadata_content("DC.publisher", soup),
        publishedDate = OAI_metadata_content("DC.date", soup),
        description = OAI_metadata_content("DC.description", soup),
        infoLink = url,
        publicDomain = True,
        language = normalize_to_ascii(get_lang(source)),
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
    redis_py.set(output_file_key, output_file, True)
        
   
def download_book(Id, id_for_key):  
    """Download book images and tar them to one file"""   
    Id = get_id_from_string(Id)
    Id_raw = get_id_from_string(Id, action = 'desanitize')
    total_pages = extract_total_pages(Id_raw)
    start_page_no = 0
    s = requests.Session()
    for page_no in range(0, total_pages+1):
        image_url = "http://gallica.bnf.fr/%s/f%s.highres" %(Id_raw, start_page_no + page_no)
        output_file =  add_serial_number_to_name("/data/scratch/BUB_downloads/gal_%s_" %Id, page_no)
        status = download_image_to_file(image_url, output_file)
	if status == 1:
	    return 1
    final_output_file = "/data/scratch/BUB_downloads/bub_gal_%s_images.tar" %Id
    command = "tar -cf %s --directory=/data/scratch/BUB_downloads/ $(ls /data/scratch/BUB_downloads/gal_%s_*| xargs -n1 basename)" %(final_output_file, Id)
    status = subprocess.check_call(command, shell=True)
    store_output_file_name(id_for_key, final_output_file)
    if status == 0:
        command = "rm /data/scratch/BUB_downloads/gal_%s_*" %(Id)
        status = subprocess.check_call(command, shell=True)
    return 0

 
def get_lang(source):
    l = re.findall("language.label.([\S]+) ", source)
    if len(l)>0:
        return l[0]
    else:
        return ""
 
def extract_total_pages(Id_raw):
    r = requests.get('http://gallica.bnf.fr/%s' %Id_raw)
    no= re.findall('Nombre total de vues : ([\d]+)',  r.text)
    if len(no) >0:
        return int(no[0])
    else:
        return None        
 
