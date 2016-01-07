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
from requests_oauthlib import OAuth1
#import requests  --  imported from retry (with retry wrapper)

from BeautifulSoup import BeautifulSoup

sys.path.append('./utils')
sys.path.append('../utils')
import keys, redis_py
from retry import retry, requests


log = open('/data/project/bub/public_html/BUB/bot/ht.log', 'a')

    
def get_record_key_from_id(Id):
    """Extract and return record key associated with the book-id"""
    r = requests.get("http://catalog.hathitrust.org/api/volumes/brief/htid/%s.json" %Id)
    if r.status_code != 200:
        return ""
    info = r.json()
    record_key = info['records'].keys()
    if record_key not in (None, ""):
        return record_key[0]
    else:
        return ""    


def get_id_from_string(s):
    """Return book ID from a string (can be a book code or URL)."""
    if "." not in s:
        return s
    elif len(re.findall('\.',s)) == 1 and '/' not in s:
        record_key = get_record_key_from_id(s)
        if record_key != "":
            return record_key
        else:
            return None
    else:
        match = re.search("[?&]?id=([^\[&;\]]+)", s)
        if match:
            record_key = get_record_key_from_id(match.group(1))
            if record_key != "":
                return record_key
            else:
                return None
        else:
            match = re.search("/Record/(\d+)", s)
            if match:
                return match.group(1)
            else:
                return None
    

def verify_id(Id_string):
    """Verify the Id and public-domain status for the book"""
    Id = get_id_from_string(Id_string)
    if Id == None:
        return 1
    try:
        r = requests.get("http://catalog.hathitrust.org/api/volumes/full/recordnumber/%s.json" %Id)
    except:
        return 10
    if r.status_code != 200:
        return 10
    else:
        book_info = r.json()
        items = book_info["items"]
        if items == []:
            return 10
        if items[0]["usRightsString"] != "Full view":
            return 2
        if """<subfield code="s">google</subfield>""" in str(book_info):
            return 9
        else:
            return 0


def extract_language(soup):         #needs improvement as language returned in codes.
    """Extract and return language associated with the book"""
    for no, i in enumerate(soup.findAll('controlfield', attrs=dict(tag="008"))[0].text[-3::-1]):
        if not i.isalpha():
            return soup.findAll('controlfield', attrs=dict(tag="008"))[0].text[-(2+no):-3]
    return ""
    
    
def extract_author(soup):
    """Extract and return author associated with the book"""
    author_data = soup.findAll('datafield', attrs=dict(tag="100"))
    if author_data != []:
        return author_data[0].text
    return ""
    
    
def extract_publisher(soup):
    """Extract and return publisher associated with the book"""
    publisher_data = soup.findAll('datafield', attrs=dict(tag="260"))
    if publisher_data != []:
        return publisher_data[0].text
    return ""
 
    
def extract_total_pages(Id):
    """Extract and return total pages in the book"""
    r = requests.get("http://babel.hathitrust.org/cgi/pt?id=%s" %Id)
    source = r.text
    soup = BeautifulSoup(source)
    last = soup.findAll('a', attrs={'id':"action-go-last"})
    if last != []:
        last_page_url = last[0]['href']
        last_page_no = re.search("seq=(\d+)", last_page_url)
        return int(last_page_no.group(1))


def metadata(Id):
    """Return book information and meta-data"""    
    Id = get_id_from_string(Id)
    r = requests.get("http://catalog.hathitrust.org/api/volumes/full/recordnumber/%s.json" %Id)
    if r.status_code != 200:
        return 10    
    else:
        book_info = r.json()
        items = book_info["items"]
        records = book_info["records"][book_info['records'].keys()[0]]       
        if items == []:
            return 10
        if items[0]["usRightsString"] != "Full view":
            return 2
    xml = records["marc-xml"]
    soup = BeautifulSoup(xml)
    htid = items[0]["htid"]
    return dict(
        image_url = "http://babel.hathitrust.org/cgi/imgsrv/image?id=%s;seq=1;width=300" %htid,
        thumbnail_url = "http://babel.hathitrust.org/cgi/imgsrv/image?id=%s;seq=1;width=128" %htid,
        printType = "BOOK",
        title = records['titles'][0],
        subtitle = "",
        author = extract_author(soup),
        publisher = extract_publisher(soup),
        publishedDate = records["publishDates"][0] if "publishDates" in records.keys() else "",
        description = records['titles'][0] if "titles" in records.keys() else "",
        infoLink = records["recordURL"] if "recordURL" in records.keys() else "",
        publicDomain = True if items[0]["rightsCode"] in ("pd", "pdus") else "",
        language = extract_language(soup),
        scanner = "Hathitrust",
        sponser = "HathiTrust"
    )


@retry(logger = log)
def download_image_to_file(image_url, output_file):
    "Download image from url"
    client_key = keys.hathitrust_api_access_key
    client_secret = keys.hathitrust_api_secret_key
    oauth = OAuth1(client_key=client_key, client_secret=client_secret, signature_type='query')
    rsession = requests.Session()
    rsession.auth = oauth
    r=rsession.get(image_url, params=dict(v='2'),stream=True)
    if r.status_code == 200:
        image_type = r.headers['content-type']
        if image_type == 'image/jpeg':
            image_ext = 'jpeg'
	elif image_type == 'image/png':
              image_ext = 'png'
        else:
            image_ext = re.search('image/(.+)',image_type).group(1)
        output_file += image_ext        
        with open(output_file, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk) 
    else:
	log.write(r.text)
	log.flush()
        log.write(image_url)
        log.flush()
	return 1


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
    book_key = redis_key3+":ht:%s" %Id
    output_file_key = book_key + ":output_file"
    redis_py.set(output_file_key, output_file, True)


def get_id_from_record_key(Id):
    """Extract and return htid associated with the book"""
    r = requests.get("http://catalog.hathitrust.org/api/volumes/brief/recordnumber/%s.json" %Id)
    book_info = r.json()
    htid = book_info["items"][0]["htid"]
    return htid
             
                
def download_book(Id):  
    """Download book images from HathiTrust and tar them to one file"""   
    s = requests.Session()
    Id_key = get_id_from_record_key(Id)
    r = requests.get("http://babel.hathitrust.org/cgi/pt?id=%s" %Id_key)
    total_pages = extract_total_pages(Id_key)
    for page_no in range(1, total_pages+1):
        image_url = "https://babel.hathitrust.org/cgi/htd/volume/pageimage/%s/%s"%(Id_key, page_no)
        #output_file = "./downloads/ht_%s_%s." %(Id, page_no)
        output_file =  add_serial_number_to_name("/data/scratch/BUB_downloads/ht_%s_" %Id, page_no)
        status = download_image_to_file(image_url, output_file)
	if status == 1:
	    return 1
    final_output_file = "./downloads/bub_ht_%s_images.tar" %Id
    command = "tar -cf %s --directory=/data/scratch/BUB_downloads/ $(ls /data/scratch/BUB_downloads/ht_%s_*| xargs -n1 basename)" %(final_output_file, Id)
    status = subprocess.check_call(command, shell=True)
    store_output_file_name(Id, final_output_file)
    if status == 0:
        command = "rm /data/scratch/BUB_downloads/ht_%s_*" %(Id)
        status = subprocess.check_call(command, shell=True)
    return 0        

