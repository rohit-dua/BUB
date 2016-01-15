#!../flask/bin/python
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


import sys
import MySQLdb
import json
import dateutil.parser as parser
from datetime import datetime
import difflib
import os.path
from os import urandom
import re
#import requests  --  imported from retry (with retry wrapper)
import time
from urllib import quote_plus
import subprocess
import hashlib

import internetarchive as ia

sys.path.append('../utils')
sys.path.append('./utils')
import redis_py
import mysql_py
import keys
from retry import retry, ia_online, requests

sys.path.append('../app')
import bridge


log = open('worker.log', 'a')


def lang_code(code):
    """Return language name corresponding to its code"""
    language = {
        'hy':'Armenian',
        'bg':'Bulgarian',
        'ca':'Catalan',
        'zh-CN':'Chinese',
        'zh-TW':'Chinese',
        'hr':'Croatian',
        'cs':'Czech',
        'da':'Danish',
        'nl':'Dutch',
        'en':'English',
        'fi':'Finnish',
        'fr':'French',
        'de':'German',
        'el':'Greek',
        'hi':'Hindi',
        'hu':'Hungarian',
        'is':'Icelandic',
        'id':'Indonesian',
        'it':'Italian',
        'ja':'Japanese',
        'ko':'Korean',
	'la':'Latin',
        'lv':'Latvian',
        'lt':'Lithuanian',
        'no':'Norwegian',
        'pl':'Polish',
        'pt-BR':'Portuguese',
        'pt-PT':'Portuguese',
        'ro':'Romanian',
        'ru':'Russian',
        'sr':'Serbian',
        'sk':'Slovak',
        'sl':'Slovenian',
        'es':'Spanish',
        'sv':'Swedish',
        'th':'Thai',
        'tr':'Turkish',
        'uk':'Ukrainian',    
    }
    code = difflib.get_close_matches(code, language.keys(), 1)
    try:
        return language[code[0]]
    except:
        return code[0]


class IaWorker(object):
    """Internet-archive worker: ia-check, upload, call download method from library module"""
    
    def __init__(self, value):
        """Assign variable, and get metadata from cache"""
        redis_key3 = keys.redis_key3
        self.redis_key3 = redis_key3
        self.redis = redis_py.Redis()
        if  isinstance(value, (int, long, float, complex)):
            db = mysql_py.Db()
            values = db.execute('select library, book_id from request where sno = %s;',value)[0]
            db.close()
            self.library = values[0]
            self.Id = values[1].encode('utf-8')
            self.book_key = "%s:%s:%s" %(redis_key3, self.library, self.Id) 
            self.redis.set(redis_key3+":ongoing_job_identifier", self.Id)
            self.ia_identifier = None
	    self.id_for_key = self.Id
        else:
            self.library = value['library']
            self.Id = value['Id']
            self.ia_identifier = "bub_" + self.library + "_" + value['ia_identifier_suffix']
            self.book_key = "%s:%s:%s" %(redis_key3, self.library, value['ia_identifier_suffix']) 
            self.redis.set(redis_key3+":ongoing_job_identifier", value['ia_identifier_suffix'])
	    self.id_for_key = value['ia_identifier_suffix']
        if '/' not in self.id_for_key:
            self.redis_output_file_key = "%s:%s:%s:output_file" %(redis_key3, self.library, self.id_for_key)
        else:
            self.redis_output_file_key = "%s:%s:%s:output_file" %(redis_key3, self.library, hashlib.md5(self.id_for_key).hexdigest())
        self.library_name = bridge.lib_module(self.library)[1]           
        metadata_key = self.book_key + ":meta_data"
        metadata = redis_py.get(metadata_key, True)
        info = json.loads(metadata)      
        try:
            self.title = info['title'].encode("utf-8") + " " + info['subtitle'].encode("utf-8")
        except:
            self.title = str(info['title'].encode("utf-8")) + " " + str(info['subtitle']) 
        self.author = info['author'].encode("utf-8")
        self.publisher = info['publisher'].encode("utf-8")
        self.description = info['description'].replace("\n", "").encode("utf-8")
        self.printType = info['printType'].encode("utf-8")
        self.publishedDate = re.sub("[^0123456789/.-]","", info['publishedDate'].encode("utf-8"))
        self.infoLink = info['infoLink']
        self.publicDomain = info['publicDomain']
        language_code = info['language'].encode("utf-8")
        if self.publishedDate not in (None,"") :
            try:
                self.publishedDate = re.sub('[x?]','0',self.publishedDate)
                self.year = parser.parse(self.publishedDate).year
                self.month = parser.parse(self.publishedDate).month
                self.day = parser.parse(self.publishedDate).day
            except:
                self.year = ""
                self.month = ""
                self.day = "" 
        else:
            self.year = ""
            self.month = ""
            self.day = ""  
        try:
            self.language = lang_code(language_code)
        except:
            self.language = ""
        self.pdf_path = "/data/scratch/BUB_downloads/bub_%s_%s.pdf" %(self.library, self.Id)
        self.scanner = info['scanner'] 
        self.sponser = info['sponser']        
        
        
    #@retry(backoff = 2, logger = log)
    @ia_online(logger = log)
    def check_in_IA(self, library, Id):
        """Check if book present in IA.
        Return False if not present else Return Identifier(s)"""
        
        url="""http://archive.org/advancedsearch.php?q=title%%3A(%s)+AND+mediatype%%3A(texts)&fl[]=creator&fl[]=source&fl[]=date&fl[]=identifier&fl[]=language&fl[]=publisher&fl[]=title&sort[]=&sort[]=&sort[]=&rows=20&page=1&output=json""" % quote_plus(re.sub(r"""[!#\n|^\\\"~()\[\]:\-/]""", '', self.title)[:330])  
        r = requests.get(url)
        ia_info = r.json()
        numFound = int(ia_info['response']['numFound'])
        if numFound > 20:
            numFound = 20
        if numFound == 0:
	    ia_response_key = self.book_key + ":ia_response"
	    redis_py.set(ia_response_key, 0, True)
            return False
        match_list = []
        year_present = 0
        self.magazine = 0
        for i in range(numFound):
            match_score = 0
            creator_present = 0 
	    #print "index: %s\n" %i
            if 'source' in ia_info['response']['docs'][i].keys() and self.Id not in (None, ""):
                source = ia_info['response']['docs'][i]['source'].encode("utf-8")
		#print "source: %s" %source
                if self.Id in source:
                    match_score += 20 
            if 'title' in ia_info['response']['docs'][i].keys() and self.title not in (None, ""):
                title = ia_info['response']['docs'][i]['title'].encode("utf-8")
                title_similarity = difflib.SequenceMatcher(None, self.title.lower(), title.lower()).ratio() 
                match_score += 50*title_similarity                 
            if 'date' in ia_info['response']['docs'][i].keys():
                if parser.parse( ia_info['response']['docs'][i]['date'] ).year == self.year:
                    if self.printType != 'MAGAZINE':
                        match_score += 25
                        year_present = 1
                    else:
                        self.magazine = 1
                        if parser.parse( ia_info['response']['docs'][i]['date'] ).month == self.month:
                            if parser.parse( ia_info['response']['docs'][i]['date'] ).day == self.day:
                                match_score += 25
            if 'creator' in ia_info['response']['docs'][i].keys() and self.author not in (None, ""):
                creator = ia_info['response']['docs'][i]['creator'][0].encode("utf-8")
                creator_similarity = difflib.SequenceMatcher(None, self.author.lower(), creator.lower()).ratio()  
                match_score += 12*creator_similarity   
                creator_present = 1           
            if 'publisher' in ia_info['response']['docs'][i].keys() and self.publisher not in (None, ""):
                publisher = ia_info['response']['docs'][i]['publisher'][0].encode("utf-8")
                publisher_similarity = difflib.SequenceMatcher(None, self.publisher.lower(), publisher.lower()).ratio()
                match_score += 6*publisher_similarity                               
            if 'language' in ia_info['response']['docs'][i].keys() and self.language not in (None, ""):
                l = ia_info['response']['docs'][i]['language'][0].encode("utf-8")
                if len(l) < 5:
                    try:
                        language = lang_code(l)
                    except:
                        language = l
                else:
                    language = l
                lang_similarity = difflib.SequenceMatcher(None, self.language.lower(), language.lower()).ratio()
                match_score += 3*lang_similarity  
            if self.magazine == 0:
                threshold_score = (0.7)*80 + (25)*year_present + (1 - year_present)*((0.5)*12*creator_present + (0.7)*6*(1-creator_present))
            else:
                threshold_score = (0.7)*80 + 25             
            match_list.append(ia_info['response']['docs'][i]['identifier'])                     
        if match_list != []:
            ia_response_key = self.book_key + ":ia_response"
            redis_py.set(ia_response_key, 1, True)
            return match_list
        ia_response_key = self.book_key + ":ia_response"
        redis_py.set(ia_response_key, 0, True) 
        return False    
    
    #@retry(tries = 4, delay = 5, logger = log, backoff = 2)
    @ia_online(logger = log)
    def get_valid_identifier(self, primary = True):
        """Iterate over identifiers suffixed by _<no>, until found."""
        if self.ia_identifier:
            ia_key = self.ia_identifier
        else:
            ia_key = "%s_%s_%s" %('bub', self.library, self.Id)
        item = ia.get_item(ia_key)
        if item.exists == False and primary == True:
            return item
        for index in range(2,10):
            item = ia.get_item("%s_%s" %(ia_key, index))
            if item.identifier == self.ia_identifier:
                continue
            if item.exists == False:
                return item
        item = ia.get_item(urandom(16).encode("hex"))
        return item
        
        
    #@retry(logger = log, backoff = 2)
    @ia_online(logger = log)
    def upload_to_IA(self, library, Id): 
        """Upload book to IA with appropriate metadata."""
        if self.ia_identifier == None:
            item = self.get_valid_identifier()
            self.ia_identifier = item.identifier
        else:
            item = ia.get_item(self.ia_identifier)
        metadata = dict(
            mediatype = "text",
            creator = self.author,
            title = re.sub(r"""[!#\n\r|^\\\"~()\[\]:\-/]""",'',self.title)[:330],
            publisher = self.publisher,
            description = re.sub(r"""[!#\n\r|^\\\"~()\[\]:\-/]""",'',self.description),
            source = self.infoLink,
            language = self.language,
            year = self.year,
            date = self.publishedDate,
            subject = "bub_upload",
            licenseurl = "http://creativecommons.org/publicdomain/mark/1.0/" if self.publicDomain == True else "",
            scanner = self.scanner,
            sponsor = self.sponser,
            uploader = "bub")
        metadata['google-id'] = self.Id if self.library == 'gb' else ""
        filename = redis_py.get(self.redis_output_file_key, True)
        S3_access_key = keys.S3_access_key
        S3_secret_key = keys.S3_secret_key
        try:
            status = item.upload(filename, access_key = S3_access_key, secret_key = S3_secret_key, metadata=metadata)
        except:
             item = self.get_valid_identifier(primary = False)
             self.ia_identifier = item.identifier
             status = item.upload(filename, access_key = S3_access_key, secret_key = S3_secret_key, metadata=metadata)
        command = "rm %s" %(filename)
        try:
            subprocess.check_call(command, shell=True)     
        except:
            log.write("%s  Command rm %s failed" %(datetime.now(), filename))
            log.flush()      
        return status

    def save_ia_identifier(self, value):
        """Save Ia-Identifier for caching purpose."""
        redis_key3 = keys.redis_key3
        key_ia_identifier = self.book_key + ":ia_identifier"      
        value = json.dumps(value)
        redis_py.set(key_ia_identifier, value, True) 

    def submit_OCR_wait_job(self, value):
        """Add book-request to OCR-waitlist queue"""     
        self.save_ia_identifier(value)
        redis_key2 = keys.redis_key2
        q = redis_py.Queue(redis_key2)
        q.add( self.book_key )   
    
    
class QueueHandler(object):
    def __init__(self, redis_key):
        self.queue = redis_py.Queue(redis_key)
    
    def pop_and_remove(self):
        """Pop and remove an item from redis queue 
        when available(blocking)"""
        item = False
        while item is False:
            item = self.queue.pop()
            if item != False:
                self.queue.remove(item[0])
            if item is False:
                time.sleep(1)
        return json.loads(item[0])
        

def manager(q):
      while True:
        value = q.pop_and_remove()    
        ia_w = IaWorker(value)
        if isinstance(value, (int, long, float, complex)):
            ia_identifier_found = ia_w.check_in_IA(ia_w.library, ia_w.Id)
            if ia_identifier_found is not False:
                ia_w.submit_OCR_wait_job(ia_identifier_found)
                continue
        else:
            ia_response_key = ia_w.book_key + ":ia_response"
            redis_py.set(ia_response_key, 3, True)       
        if not os.path.isfile(ia_w.pdf_path):
            download_status = bridge.download_book(ia_w.library, ia_w.Id, ia_w.id_for_key)
            if download_status != 0:
                log.write("%s  Download Error, library:%s, ID:%s\n" %(datetime.now(), ia_w.library, ia_w.Id) )
                log.flush()
                continue
        download_progress_key = ia_w.book_key + ":download_progress"
        redis_py.set(download_progress_key, 1, True)   
        upload_status = ia_w.upload_to_IA(ia_w.library, ia_w.Id)
        if str(upload_status) == "[<Response [200]>]":
            upload_progress_key = ia_w.book_key + ":upload_progress"
            redis_py.set(upload_progress_key, 1, True)
            ia_w.submit_OCR_wait_job(ia_w.ia_identifier)
        ia_w.redis.delete(ia_w.redis_key3+":ongoing_job_identifier")            
        
def main():
    log.write("%s  Started worker.py\n" %datetime.now())
    log.flush()
    redis_key1 = keys.redis_key1 
    q = QueueHandler(redis_key1)  
    manager(q)            
        
        
if __name__ == '__main__':
    sys.exit(main())
        
