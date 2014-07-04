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


import sys
import MySQLdb
import json
import dateutil.parser as parser
import difflib
import os.path
import re
import requests
import multiprocessing
import time

sys.path.append('../lib')
import internetarchive as ia
import redis_py
import mysql_py

sys.path.append('../app')
import bridge


def lang_code(code):
    """Return language corresponding to its code"""
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
        return code


def submit_to_redis_list(fields, value):
    """Add value to redis list(leftmost)
     and name of list to redis queue"""
    json_data = open('../../settings.json')
    settings = json.load(json_data)
    Redis_Key = settings['redis']['key_3']
    list_name = "%s:%s:%s" %(Redis_Key, fields.library, fields.Id)
    redis = redis_py.Redis()        
    redis.lpush(list_name, value)     
    Redis_Key = settings['redis']['key_2']
    q = redis_py.Queue(Redis_Key)
    q.add( list_name )


class ia_worker(object):
    """Internet-archive worker: perform upload/ file checks/ metadata extraction"""
    def __init__(self, sno):
        """Get metadata"""
        db = mysql_py.db()
        values = db.execute('SELECT LIBRARY,ID FROM REQUESTS WHERE SNO = %s;',sno)
        db.close()
        self.library = values[0]
        self.Id = values[1]       
	self.library_name = bridge.lib_module(self.library)[1]
        info = bridge.book_info(self.library, self.Id)
        self.title = info['title'].encode("utf-8") + " " + info['subtitle'].encode("utf-8")
        self.author = info['author'].encode("utf-8")
        self.publisher = info['publisher'].encode("utf-8")
        self.description = info['description'].replace("\n", "").encode("utf-8")
        self.printType = info['printType'].encode("utf-8")
        self.publishedDate = info['publishedDate'].encode("utf-8")
        language_code = info['language'].encode("utf-8")
        if self.publishedDate not in (None,"") :
            self.year = parser.parse(self.publishedDate).year
            self.month = parser.parse(self.publishedDate).month
            self.day = parser.parse(self.publishedDate).day
        else:
            self.year = ""
            self.month = ""
            self.day = ""  
        try:
            self.language = lang_code(language_code)
        except:
            self.language = ""
        self.ia_identifier = "bub_%s_%s" %(self.library, self.Id)
        self.pdf_path = "./downloads/%s_%s.pdf" %(self.library, self.Id)
	#logging.info("called ia_worker")
        
     
    def check_in_IA(self):
        """Check if book present in IA.
        Return False if not present else Return Identifier"""
        r = requests.get("""http://archive.org/advancedsearch.php?q=identifier%%3A%s&[]=identifier&sort[]=&sort[]=&sort[]=&
        rows=10&page=1&output=json""" %self.ia_identifier )
        ia_info = r.json()
        if int(ia_info['response']['numFound']) != 0:
            if ia_info['response']['docs'][0]['identifier'] == self.ia_identifier:
                #logging.info("%s uploaded by BUB on IA" %self.ia_identifier)
                return self.ia_identifier
	#logging.info("%s not Uploaded to IA using bub." %self.ia_identifier)
        r = requests.get("""http://archive.org/advancedsearch.php?q=%s&fl[]=creator&fl[]=date&fl[]=identifier&fl[]=language&
	fl[]=publisher&fl[]=title&sort[]=&sort[]=&sort[]=&rows=20&page=1&output=json""" % re.sub(r"""[!#\n|^\\\"~()\[\]\-]""", '', self.title)[:365] )
        ia_info = r.json()
        numFound = int(ia_info['response']['numFound'])
        if numFound > 20:
            numFound = 20
        if numFound == 0:
	    #logging.info("%s not Uploaded on IA" %self.ia_identifier)
            return False
        score_card = []
        year_present = 0
        self.magazine = 0
        for i in range(numFound):
            match_score = 0
            creator_present = 0 
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
            score_card.append( [match_score, threshold_score] )
        max_score = max(score_card)    
        if max_score[0] > max_score[1]:
            #logging.info("found on IA %s" %ia_info['response']['docs'][score_card.index(max_score)]['identifier'])
            return ia_info['response']['docs'][score_card.index(max_score)]['identifier']
        else:
	    #logging.info(" %s not Uploaded on IA" %self.ia_identifier)
            return False    

        
    def upload_to_IA(self): 
        """Upload book to IA with appropriate meta-data."""
        item = ia.get_item(self.ia_identifier)
        metadata = dict(
          mediatype = "text",
          creator = self.author,
	  title = re.sub(r"""[!#\n|^\\\"~()\[\]\-]""",'',self.title)[:365],
          publisher = self.publisher,
          description = re.sub(r"""[!#\n|^\\\"~()\[\]\-]""",'',self.description),
          source = self.library_name,
          language = self.language,
          year = self.year,
          date = self.publishedDate,
          subject = "bub_upload",
	  licenseurl = "http://creativecommons.org/publicdomain/mark/1.0/",
	  scanner = self.library_name,
          Digitizing_sponsor = self.library_name )
        filename = "./downloads/%s_%s.pdf" %(self.library, self.Id)
        json_data = open('../../settings.json')
        settings = json.load(json_data)
        S3_access_key = settings['ia']['S3_access_key']
        S3_secret_key = settings['ia']['S3_secret_key']
        status = item.upload(filename, access_key = S3_access_key, secret_key = S3_secret_key, metadata=metadata)
	#logging.info("%s uploaded to IA" %self.ia_identifier)
        return status
        

class queueHandler(object):
    def __init__(self, redis_key):
        self.queue = redis_py.Queue(redis_key)
    
    def pop_and_remove(self):
        """Pop and remove an item from redis queue 
        when available(blocking)"""
        item = False
        while item is False:
            #LOCK.acquire() for multiprocessing
            item = self.queue.pop()
            if item != False:
                self.queue.remove(item[0])
            #LOCK.release()
            if item is False:
                time.sleep(1)
        return item[0]
        

def manager(q):
    while True:
        sno = q.pop_and_remove()
        print "GOT SNO:"+str(sno)
        ia_w = ia_worker(sno)
        ia_identifier_found = ia_w.check_in_IA()
        if ia_identifier_found is not False:
            submit_to_redis_list(ia_w, ia_identifier_found)
            continue
        if not os.path.isfile(ia_w.pdf_path):
            download_status = bridge.download_book(ia_w.library, ia_w.Id)
            if download_status != 0:
                continue
	#logging.error("Download error id: %s, library: %s" %(ia_w.Id,ia_w.library) )   
        upload_status = ia_w.upload_to_IA()
        if str(upload_status) == "[<Response [200]>]":
            submit_to_redis_list(ia_w, ia_w.ia_identifier)
	#logging.info( "IA upload:" + str(upload_status))
 
        
def main():
    #logging.info("worker.py started")
    json_data = open('../../settings.json')
    settings = json.load(json_data)
    redis_key = settings['redis']['key_1']  
    q = queueHandler(redis_key)  
    manager(q)            
        
        
if __name__ == '__main__':
    sys.exit(main())
        
        
