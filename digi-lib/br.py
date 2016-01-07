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
import unicodedata
import sys
#import requests  --  imported from retry (with retry wrapper)

sys.path.append('./utils')
sys.path.append('../utils')
import keys, redis_py
from retry import requests


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
        Id = re.sub('/', '_', Id)
    elif action == 'desanitize':
        Id = re.sub('_', '/', Id)
    return Id
        

def get_id_from_string(s, action = 'sanitize'):
    """Return book ID from a string (can be a book code or URL)."""
    if "." not in s:
        if action == 'sanitize':
            s = sanitize_id_to_url(s)
        else:
            s= sanitize_id_to_url(s, 'desanitize')
        return s
    url = s
    match = re.search("/handle/([^(&/#?)]+/[^(&/#?)]+)", url)
    if not match:
        return None
    Id = match.group(1)
    if action == 'sanitize':
        Id = sanitize_id_to_url(Id)
    else:
        Id = sanitize_id_to_url(Id, 'desanitize')
    return Id
    

def OAI_metadata_content(name, soup):
    """Extract and return the specified meta-tags value"""
    meta_value = soup.findAll('meta', attrs=dict(name=name))
    if meta_value != []:
        return meta_value[0].get('content')
    else:
        return ""
      
        
def extract_item_number(source):
    """Extract and return the item number (from the html source) associated with the book"""
    item_number = re.search('qsParm\["item"\]\s*=\s*"(.+)"', source)
    if item_number:
        return item_number.group(1)
    else:
        return ""

    
def extract_serverURL(source):
    """Extract and return server url (from the html source) associated with the book"""
    serverURL =  re.search('qsParm\["serverURL"\]\s*=\s*"(.+)"', source)
    if serverURL:
        return serverURL.group(1) 
    else:
        return ""


def extract_downloadURL(source):
    """Extract and return book_pdf url (from the html source) associated with the book"""
    downloadURL =  re.search('qsParm\["downloadURL"\]\s*=\s*"(.+)"', source)
    if downloadURL:
        return "http://www.brasiliana.usp.br" + str(downloadURL.group(1)) 
    else:
        return ""


def verify_id(Id_string):
    """Verify the Id and public-domain status for the book"""
    Id = get_id_from_string(Id_string, 'desanitize')
    if Id == None:
        return 1
    try:
        r = requests.get("http://www.brasiliana.usp.br/bbd/handle/%s" %Id)
    except:
        return 1
    if r.status_code == 404:
	return 1
    if r.status_code != 200:
        return 10
    else:
        source = r.text
        if "Página não encontrada".decode('utf-8') in source:
            return 1
        soup = BeautifulSoup(source)
        if OAI_metadata_content("DC.relation", soup) != "Domínio público".decode('utf-8'):
            return 2
        else:
            return 0


def metadata(Id):
    """Return book information and meta-data"""
    Id = get_id_from_string(Id, 'desanitize')
    url = "http://www.brasiliana.usp.br/bbd/handle/%s" %Id
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
        if "Página não encontrada".decode('utf-8') in source:
            return 1
        soup = BeautifulSoup(source)
        if OAI_metadata_content("DC.relation", soup) != "Domínio público".decode('utf-8'):
            return 2
    png_url = "%s?url_ver=Z39.88-2004&rft_id=%s&svc_id=info:lanl-repo/svc/getRegion&svc_val_fmt=info:ofi/fmt:kev:mtx:pdf&svc.format=image/png&svc.clayer=0&svc.level=" %(extract_serverURL(source), extract_item_number(source) ) 
    return dict(
        image_url = png_url + "1",
        thumbnail_url = png_url + "0",
        printType = "BOOK",
        title = OAI_metadata_content("DC.title", soup),
        subtitle = "",
        author = OAI_metadata_content("DC.creator", soup),
        publisher = OAI_metadata_content("DC.publisher", soup),
        publishedDate = OAI_metadata_content("DCTERMS.issued", soup),
        description = OAI_metadata_content("DC.description", soup),
        infoLink = url,
        publicDomain = True,
        language = normalize_to_ascii(OAI_metadata_content("DC.language", soup)),
        scanner = "brasiliana.usp.br",
        sponser = "brasiliana.usp.br"
    )


def store_output_file_name(Id, output_file):
    """Save output file name to redis-memory"""
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = redis_key3+":br:%s" %Id
    output_file_key = book_key + ":output_file"
    redis_py.set(output_file_key, output_file, True)


def download_book(Id):
    Id_raw = sanitize_id_to_url(Id, action = 'desanitize')
    url = "http://www.brasiliana.usp.br/bbd/handle/%s" %Id_raw
    r = requests.get(url)
    source = r.text
    pdf_url = extract_downloadURL(source)
    pdf = requests.get(pdf_url, stream=True)
    output_file = "/data/scratch/BUB_downloads/bub_br_%s.pdf" %Id ###
    store_output_file_name(Id, output_file) 
    with open(output_file, 'wb') as f:
        for chunk in pdf.iter_content(1024):  
            f.write(chunk)  
    return 0            

