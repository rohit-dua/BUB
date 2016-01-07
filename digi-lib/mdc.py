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
import HTMLParser
import subprocess
import sys
#import requests  --  imported from retry (with retry wrapper)

from tld import get_tld

sys.path.append('./utils')
sys.path.append('../utils')
import keys, redis_py
from retry import retry, requests
        


def get_id_from_string(s):
    """Return book ID from a string (can be a book code or URL)."""
    if '/' not in s:
        return s
    url = s
    match = re.search("/collection/(.+)/id/([^/?&]+)", url)
    if not match:
        return None
    try:
        Id = match.group(1) + "_" + match.group(2)
    except:
        return  None
    return Id
    

def remove_leading_space(text):
    if text[0] == ' ':
        return text[1:]
    return text
    

def get_meta(attribute, soup):
    content = ""
    meta = soup.findAll('td', attrs={'id' : attribute})
    h = HTMLParser.HTMLParser()
    if meta:   
        text = meta[0].contents
        if text != []:
            for i in text:
                try:
                    content = content + " " + i.text
                except AttributeError:
                    if len(i.split() ) == 0:
                        continue
                    content = content + " " + i
            content = h.unescape(content)
            return remove_leading_space(content)
        return remove_leading_space( h.unescape(meta[0].text) )
    return ""
    
    
def extract_total_pages(soup):
    data = soup.findAll('input', attrs={'id' : "cdm_cpd_itemcount"})
    if data == []:
        return None
    return int(data[0].get('value'))


def verify_id(Id_string):
    """Verify the Id and public-domain status for the book"""
    Id = get_id_from_string(Id_string)
    if Id == None:
        return 1
    unique_id = re.search('(.+)_(\d+)', Id)
    if not unique_id:
        return 1
    collection, identifier = unique_id.group(1), unique_id.group(2)
    try:
        r = requests.get("http://mdc.cbuc.cat/cdm/compoundobject/collection/%s/id/%s/rec/" %(collection, identifier))
    except:
        return 1
    if r.status_code == 404:
	return 1
    if r.status_code != 200:
        return 10
    else:
        source = r.text
        soup = BeautifulSoup(source)
        if 'Text' not in get_meta('metadata_object_type', soup):
            return 10
        else:
            return 0


def metadata(Id):
    """Return book information and meta-data"""
    Id = get_id_from_string(Id)
    unique_id = re.search('(.+)_(\d+)', Id)
    collection, identifier = unique_id.group(1), unique_id.group(2)
    url = "http://mdc.cbuc.cat/cdm/compoundobject/collection/%s/id/%s/rec/" %(collection, identifier)
    
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
        if 'Text' not in  get_meta('metadata_object_type', soup):
            return 10 
    return dict(
        image_url = "http://mdc.cbuc.cat/utils/getthumbnail/collection/%s/id/%s" %(collection, identifier),
        thumbnail_url = "http://mdc.cbuc.cat/utils/getthumbnail/collection/%s/id/%s" %(collection, identifier),
        printType = "BOOK",
        title = get_meta('metadata_object_title', soup),
        subtitle = "",
        author = get_meta('metadata_object_creato', soup),
        publisher = get_meta('metadata_object_publis', soup),  
        publishedDate = get_meta('metadata_object_date', soup),
        description = "",
        infoLink = url,
        publicDomain = True,
        language = get_meta('metadata_object_langua', soup),
        scanner = "Digital Memory of Catalonia",
        sponser = "Digital Memory of Catalonia"
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
        if image_type == 'image/jpeg':
            image_ext = 'jpeg'
        else:
          if image_type == 'image/png':
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
    book_key = redis_key3+":mdc:%s" %Id
    output_file_key = book_key + ":output_file"
    redis_py.set(output_file_key, output_file, True)


def extract_downloadURL(tld, soup):
    pdf_url = soup.findAll('embed')
    pdf_url = pdf_url[0].get('src')
    if pdf_url[0] == '/':
        pdf_url = tld + pdf_url
    return pdf_url


def extract_base_domain(url):
    """Extract and return the base domain name from the url."""
    tld = get_tld(url)
    u = re.search('.+%s' %tld, url)
    if u:
        return u.group()
    else:
        return ""
        
   
def download_book(Id):  
    """Download book images from HathiTrust and tar them to one file"""   
    Id = get_id_from_string(Id)
    unique_id = re.search('(.+)_(\d+)', Id)
    collection, identifier = unique_id.group(1), unique_id.group(2)
    url = "http://mdc.cbuc.cat/cdm/compoundobject/collection/%s/id/%s/rec/" %(collection, identifier)  
    r = requests.get(url)
    source = r.text
    soup = BeautifulSoup(source)  
    file_type = 'pdf' if 'pdf' in get_meta('metadata_tipus', soup) else 'image'
    if file_type == 'pdf':
        tld = extract_base_domain(url)
        if tld[-1:] == '/':
            tld = tld[:-1]
        pdf_url = "http://mdc.cbuc.cat/utils/getfile/collection/%s/id/%s/filename/1.pdf" %(collection, identifier)
        pdf = requests.get(pdf_url, stream=True)
        output_file = "/data/scratch/BUB_downloads/bub_mdc_%s.pdf" %Id ###
        store_output_file_name(Id, output_file) 
        with open(output_file, 'wb') as f:
            for chunk in pdf.iter_content(1024):  
                f.write(chunk)  
        return 0    
    
    total_pages = extract_total_pages(soup)
    start_page_no = int(identifier)-total_pages
    s = requests.Session()
    for page_no in range(0, total_pages):
        image_url = "http://mdc.cbuc.cat/utils/ajaxhelper/?CISOROOT=%s&CISOPTR=%s"\
        "&action=2&DMSCALE=100&DMWIDTH=5000&DMHEIGHT=5000&DMX=0&DMY=0&DMTEXT=&DMROTATE=0" %(collection, start_page_no + page_no)
        output_file =  add_serial_number_to_name("/data/scratch/BUB_downloads/mdc_%s_" %Id, page_no)
        status = download_image_to_file(image_url, output_file)
        print "Downloaded %s,"%output_file
	if status == 1:
	    return 1
    final_output_file = "./downloads/bub_mdc_%s_images.tar" %Id
    command = "tar -cf %s --directory=/data/scratch/BUB_downloads/ $(ls /data/scratch/BUB_downloads/mdc_%s_*| xargs -n1 basename)" %(final_output_file, Id)
    status = subprocess.check_call(command, shell=True)
    store_output_file_name(Id, final_output_file)
    if status == 0:
        command = "rm /data/scratch/BUB_downloads/mdc_%s_*" %(Id)
        status = subprocess.check_call(command, shell=True)
    return 0

