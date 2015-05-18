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
import sys
#import requests  --  imported from retry (with retry wrapper)
import hashlib

from tld import get_tld

sys.path.append('./utils')
sys.path.append('../utils')
import keys, redis_py
from retry import retry, requests



def get_id_from_string(s):
    return s
    

def get_link_and_type(url):
    p = re.search('(.*):([a-zA-Z]+)',url)
    link = p.group(1)
    link_type = p.group(2)
    if link_type == 'wildcard':
        colon_index = link.rindex(':')
        [from_no, to_no] = link[colon_index+1:].split(',')
        return (link_type, [link[:colon_index], from_no, to_no]) 
    return (link_type, link)   


def verify_id(url): 
    """Verify the Id and public-domain status for the book"""   
    (link_type, link) = get_link_and_type(url)
    if link_type == 'wildcard':
        if '(*)' not in link[0]:
            return 1
        try:
            r = requests.head(re.sub('\(\*\)', str(link[1]), link[0]))
        except:
            return 1
        if r.status_code == 404:
            return 1
        if r.status_code != 200:
            return 10
        if 'image' not in r.headers['content-type']:
            return 1
    elif link_type == 'pdf':
        try:
            r = requests.head(link)
        except:
            return 10
        if r.status_code == 404:
	        return 1
        if r.status_code != 200:
            return 10
        if 'pdf' not in r.headers['content-type']:
            return 1
    else:
        return 1
    return 0
        
  
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
        elif image_type == 'image/png':
            image_ext = 'png'
        elif image_type == 'image/jpg':
            image_ext = 'jpg'
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
    book_key = redis_key3+":man:%s" %Id
    output_file_key = book_key + ":output_file"
    redis.set(output_file_key, output_file)
    
    
def download_book(url):  
    """Download book images from GB and tar them to one file"""   
    (link_type, link) = get_link_and_type(url)
    Id = hashlib.md5(url).hexdigest()
    if link_type == 'wildcard':
        no_of_pages = int(link[2])+1 - int(link[1])
        for page_no in range(0, no_of_pages):
            image_url = re.sub('\(\*\)', str(int(link[1]) + page_no).zfill(len(link[1])) , link[0])
            output_file =  add_serial_number_to_name("./downloads/man_%s_" %Id, page_no+1)
            download_image_to_file(image_url, output_file)
        final_output_file = "./downloads/bub_man_%s_images.tar" %Id   
        command = "tar -cf %s --directory=./downloads $(ls ./downloads/man_%s_*| xargs -n1 basename)" %(final_output_file, Id)
        status = subprocess.check_call(command, shell=True)
        if status == 0:
            command = "rm ./downloads/man_%s_*" %(Id)
            status = subprocess.check_call(command, shell=True)
    elif link_type == 'pdf':
        pdf = requests.get(link, stream=True)
        final_output_file = "./downloads/bub_man_%s.pdf" %Id
        with open(final_output_file, 'wb') as f:
            for chunk in pdf.iter_content(1024):  
                f.write(chunk)         
    store_output_file_name(Id, final_output_file)    
    return 0

