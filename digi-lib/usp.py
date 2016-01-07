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

from tld import get_tld

sys.path.append('../utils')
sys.path.append('./utils')
import redis_py, keys
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
        #Id = re.sub('_', '__', Id)
        Id = re.sub('/', '_', Id)
    elif action == 'desanitize':
        Id = re.sub('_', '/', Id)
    return Id
        

def get_id_from_string(s, action = 'sanitize'):
    """Return book ID from a string (can be a book code or URL)."""
    if len(re.findall('/',s)) < 2:
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
        

def get_absolute_url_of_book(url):
    """Return the absolute url for the book excluding the relative path"""
    match = re.search("(.+/handle/[^(&/#?)]+/[^(&/#?)]+)", url)
    if match:
        return re.sub('/bitstream', '', match.group(1))
    else:
        return ""


def verify_id(Id_string): 
    """Verify the Id and public-domain status for the book"""
    Id = get_id_from_string(Id_string, 'desanitize')
    if Id == None:
        return 1
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, 'usp', Id_string)
    library_url_key = book_key + ":library_url"
    url = redis_py.get(library_url_key, True)
    url = get_absolute_url_of_book(url)
    
   
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
        #public_domain = OAI_metadata_content("DC.relation", soup)
        #if public_domain != "Domínio público".decode('utf-8') and public_domain != "":
        #return 2
        #else:
        tld = extract_base_domain(url)
        if tld[-1:] == '/':
            tld = tld[:-1]
        pdf_url = get_pdf_link(tld, soup)
        if pdf_url == False:
            return 8
        return 0


def extract_base_domain(url):
    """Extract and return the base domain name from the url."""
    tld = get_tld(url)
    u = re.search('.+%s' %tld, url)
    if u:
        return u.group()
    else:
        return ""


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
        

def metadata(Id):
    """Return book information and meta-data"""
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, 'usp', Id)
    library_url_key = book_key + ":library_url"
    url = redis_py.get(library_url_key, True)
    url = get_absolute_url_of_book(url)    
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
        #public_domain = OAI_metadata_content("DC.relation", soup)
        #if public_domain != "Domínio público".decode('utf-8') and public_domain != "":
        #return 2
    thumbnail_url = extract_thumbnail_url(soup, url)        
    return dict(
        image_url = thumbnail_url,
        thumbnail_url = thumbnail_url,
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
        scanner = extract_base_domain(url),
        sponser = extract_base_domain(url)
    )


def store_output_file_name(Id, output_file):
    """Save output file name to redis-memory"""
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = redis_key3+":usp:%s" %Id
    output_file_key = book_key + ":output_file"
    redis_py.set(output_file_key, output_file, True)    


def download_book(Id): 
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, 'usp', Id)
    library_url_key = book_key + ":library_url"
    url = redis_py.get(library_url_key, True)
    url = get_absolute_url_of_book(url)    
    r = requests.get(url)
    source = r.text
    soup = BeautifulSoup(source)
    tld = extract_base_domain(url)
    if tld[-1:] == '/':
        tld = tld[:-1]
    pdf_url = get_pdf_link(tld, soup)   
    if pdf_url in ("", None):
        return 1
    pdf = requests.get(pdf_url, stream=True)
    output_file = "/data/scratch/BUB_downloads/bub_usp_%s.pdf" %Id ###
    store_output_file_name(Id, output_file)
    with open(output_file, 'wb') as f:
        for chunk in pdf.iter_content(1024):  
            f.write(chunk)  
    return 0            
    
    
def get_pdf_link(tld, soup):
    pdf_url = OAI_metadata_content("citation_pdf_url", soup)
    pdf_links = False
    if pdf_url == "":
        links = soup.findAll('a')
        for link in links:
            if not link.has_key('href'):
                continue
            if '.pdf' in link.get('href'):
                if pdf_links == True and link.get('href') != pdf_url:
                    return False                    
                pdf_links = True
                pdf_url = link.get('href')
            else:
                continue
        if pdf_links != True:
            return False
    if pdf_url[0]== '/':
        pdf_url = tld + pdf_url
    pdf_head = requests.head(pdf_url)
    if 'content-length' in pdf_head.headers.keys():
        content_length = pdf_head.headers['content-length']
        if int(content_length) < 1000:
            return False   
        else:
            return pdf_url   
    else:
        return False  
        
    

