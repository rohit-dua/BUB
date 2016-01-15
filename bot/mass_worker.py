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
import pytz
import difflib
import os.path
from os import urandom
import re
#import requests  #--  imported from retry (with retry wrapper)
import time
from urllib import quote_plus
import subprocess
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from subprocess import Popen, PIPE
from multiprocessing import Process

import internetarchive as ia
from jinja2 import Template

sys.path.append('../utils')
import redis_py
import mysql_py
import keys
from retry import retry, ia_online, requests
from linked import get_id_from_another_worker

sys.path.append('../digi-lib')
import gb

gb.key = keys.google_books_key2
redis_key4 = keys.redis_key4  


log = open('mass_worker.log', 'a')
bulk_order_log = open('bulk_order.log', 'a')
email_log = open('email.log', 'a')


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
    """Internet-archive worker: perform metadata extraction, ia-check, upload, call download method from library module"""
    
    def __init__(self, value):
        """Assign variable"""
        redis_key3 = keys.redis_key3 
        self.library = 'gb'
        self.library_name = 'Google-Books'
        self.Id = value.encode('utf-8')
        self.ia_identifier = "bub_" + self.library + "_" + value
        self.book_key = "%s:%s:%s" %(redis_key3, self.library, value) 
        self.redis = redis_py.Redis()
        self.redis_output_file_key = "%s:%s:%s:output_file" %(redis_key3, self.library, self.Id) 
               
    def set_metadata(self): 
        """Get metadata, and save it to memory.
           Return 0 on success, or return the error_status of library module."""        
        metadata_key = self.book_key + ":metadata"
        metadata = gb.metadata(self.Id)
        if isinstance(metadata, (int, long, float, complex)):
            error_status = metadata
            return error_status
        info = metadata
        metadata = json.dumps(metadata)
        redis_py.set(metadata_key, metadata, True)  
        try:
            self.title = info['title'].encode("utf-8") + " " + info['subtitle'].encode("utf-8")
        except:
            self.title = str(info['title']) + " " + str(info['subtitle']) 
        self.author = info['author'].encode("utf-8")
        self.publisher = info['publisher'].encode("utf-8")
        self.description = info['description'].replace("\n", "").encode("utf-8")
        self.printType = info['printType'].encode("utf-8")
        self.publishedDate = re.sub("[^0123456789/.-]","", info['publishedDate'].encode("utf-8"))
        self.infoLink = info['infoLink']
        self.publicDomain = info['publicDomain']
        language_code = info['language'].encode("utf-8")
        if self.publishedDate not in (None,"") :
            self.publishedDate = re.sub('[x?]','0',self.publishedDate)
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
        self.pdf_path = "/data/scratch/BUB_downloads/bub_%s_%s.pdf" %(self.library, self.Id)
	self.scanner = info['scanner'] 
        self.sponser = info['sponser']  
        return 0      
        
    @retry(backoff = 2, logger = log)
    @ia_online(logger = log)
    def check_in_IA(self, library, Id):
        """Check if book present in IA.
        Return False if not present else Return Identifier(s)"""
        
        url="""http://archive.org/advancedsearch.php?q=title%%3A(%s)+AND+mediatype%%3A(texts)&fl[]=creator&fl[]=source&fl[]=date&fl[]=identifier&fl[]=language&fl[]=publisher&fl[]=title&sort[]=&sort[]=&sort[]=&rows=20&page=1&output=json""" % quote_plus(re.sub(r"""[!#\n|^\\\"~()\[\]:\-]""", '', self.title)[:330]) 
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
            if 'source' in ia_info['response']['docs'][i].keys() and self.Id not in (None, ""):
                source = ia_info['response']['docs'][i]['source'].encode("utf-8")
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
    
    @retry(tries = 2, delay = 5, logger = log)
    @ia_online(logger = log)
    def get_valid_identifier(self, primary = True):
        """Iterate over identifiers suffixed by _<no>, until found."""
        item = ia.get_item("%s_%s_%s" %('bub', self.library, self.Id))
        if item.exists == False and primary == True:
            return item
        for index in range(2,10):
            item = ia.get_item("%s_%s_%s_%s" %('bub', self.library, self.Id, index))
            if item.identifier == self.ia_identifier:
                continue
            if item.exists == False:
                return item
        item = ia.get_item(urandom(16).encode("hex"))
        return item
        
    @retry(logger = log, backoff = 2, tries = 4)
    @ia_online(logger = log)
    def upload_to_IA(self, library, Id): 
        """Upload book to IA with appropriate metadata."""
        if self.ia_identifier == None:
            item = self.get_valid_identifier()
            self.ia_identifier = item.identifier
        else:
            item = ia.get_item(self.ia_identifier)
        language_from_input = redis_py.get(self.book_key + ":language", True)
        metadata = dict(
            mediatype = "text",
            creator = self.author,
            title = re.sub(r"""[!#\n|^\\\"~()\[\]:\-]""",'',self.title)[:330],
            publisher = self.publisher,
            description = re.sub(r"""[!#\n|^\\\"~()\[\]:\-]""",'',self.description),
            source = self.infoLink,
            language = self.language if language_from_input in (None, "") else language_from_input,
            year = self.year,
            date = self.publishedDate,
            subject = "bub_upload",
            licenseurl = "http://creativecommons.org/publicdomain/mark/1.0/" if self.publicDomain == True else "",
            scanner = self.scanner,
            sponsor = self.sponser,
            uploader = "bub")
        metadata['google-id'] = self.Id if self.library == 'gb' else ""
        filename = redis_py.get(self.redis_output_file_key, True)
	self.filename = filename
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

    def stored_copy_check(self):
        """Check if book already uploaded by the tool."""
        if redis_py.get(self.book_key + ":upload_progress", True) == '1':
            return True  
        else:
            return None


def send_email(email, no_of_uploads):
        """Send email"""
        msg = MIMEMultipart('alternative')
        msg['From'] = "tools.bub@tools.wmflabs.org"
        msg['To'] = email 
        html_template_data = open('./templates/email.html', 'r') 
        html_template = Template(html_template_data.read())
        msg['Subject'] = "Your uploads are ready!" 
        text = """Hi!\n\nYour %s uploads are ready in Internet-archive!\n\n--\n*** This is an automatically generated email, please do not reply ***\nhttp://tools.wmflabs.org/bub/""" %no_of_uploads
        random_number = urandom(16).encode("hex")
        html = html_template.render(no_of_uploads = no_of_uploads, random = random_number)
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        p = Popen(["/usr/sbin/exim", "-odf", "-i", email], stdin=PIPE)
        p.communicate(msg.as_string())
        email_log.write('%s  Mass-Upload(%s)  %s\n' %(email, no_of_uploads, datetime.now()))
        email_log.flush()


def seconds_until_google_quota_refresh():
    """Return seconds until new Google-books quota starts.(Midnight-US/Pacific)"""
    t=datetime.now(pytz.timezone('US/Pacific')).timetuple()
    if t.tm_hour == 0:
        return 5
    return ((24.0-(t.tm_hour+t.tm_min/60.0))*3600)+3
         

class QueueHandler(object):
    def __init__(self, redis_key):
        self.queue = redis_py.Queue(redis_key)
        self.Lock = redis_py.Lock( mass_worker_key + ":pop" )
    
    def pop_and_remove(self, wait_type = 'blocking'):
        """Pop and remove an item from redis queue 
        when available(blocking)"""
        item = False
        while item is False:
            item = self.queue.pop()
            if item != False:
                self.Lock.acquire(30)
                self.queue.remove(item[0])
                self.Lock.release()
            if item is False:
                if wait_type == 'nonblocking':
                    return False
                time.sleep(1)
        return item[0]
        
    def add(self, value):
        return self.queue.add(value)


def get_shortest_queue(workers = 3):
    #2 mass-workers running
    q_size_list = []
    q_list = []
    for i in range(1, workers+1):
        worker_queue_key = "%s:mass_worker_%s" %(redis_key4, i)
        if i == 1:
            worker_queue_key = "%s:mass_worker" %(redis_key4)
        q = redis_py.Queue(worker_queue_key)
        q_list.append(q)
        q_size_list.append(q.size())
    return q_list[ q_size_list.index(min( q_size_list )) ]



def wait_and_add_to_queue(q_bulk_order):
    """Parse Id's from bulk-order queue(accepts requests from web) entry and add to mass-worker queue."""
    log.write("%s  Started wait_and_add_to_queue\n" %datetime.now())
    log.flush()
    while True:
        info = json.loads(q_bulk_order.pop_and_remove())
        ids = info[0]
        email = info[1]
        language = info[2]
        ids = re.findall(r'[^,(\r\n)\s]+', ids)
        no=len(ids)  
        q_mass_worker = get_shortest_queue()
        library_id = 'gb'
        redis_key3 = keys.redis_key3
        redis = redis_py.Redis()
        for book_id in ids:
            book_id = gb.get_id_from_string(book_id)
            book_key = "%s:%s:%s" %(redis_key3, library_id, book_id)
            book_language_key  = book_key + ":language"
            redis_py.set(book_language_key, language, True)
            q_mass_worker.add(book_id)    
        q_mass_worker.add( json.dumps((email, no)) )
        bulk_order_log.write("%s  Received %s entries from %s\n" %(datetime.now(), no, email))        
        bulk_order_log.flush()

def ping_db(db):
    """Checks and connects, if database not connected"""
    try:
        command = "select 1;"    
        db.execute(command)
    except:
        db = mysql_py.Db() 
    return db


@retry(backoff = 2, logger = log)
def manager(q_mass_worker):
      db = mysql_py.Db()
      while True:
        book_id = False
        while book_id == False:
            book_id = q_mass_worker.pop_and_remove(wait_type = 'nonblocking')  
            if book_id == False:
                book_id = get_id_from_another_worker(mass_worker_key)
                if book_id == False:
                    time.sleep(1)
        try:
            book_id = json.loads(book_id)
        except ValueError:
            pass
        if isinstance(book_id, list ):
            email = book_id[0]
            no_of_uploads = book_id[1]
            if email not in (None, ""):
                send_email(email, no_of_uploads)
            continue
        ia_w = IaWorker(book_id)        
        stored_identifier = ia_w.stored_copy_check()
        if stored_identifier != None:
            continue
        db = ping_db(db)     
        md5_book = hashlib.md5(ia_w.Id + ia_w.library).hexdigest()
        redundancy_book = db.execute("select count(*) from request where md5_book=%s and confirmed=1 and job_submitted=1;",md5_book)
        if redundancy_book[0][0] != 0:
            continue       
        metadata_status = ia_w.set_metadata()
        if isinstance(metadata_status, (int, long, float, complex)):
            if metadata_status == 7:
                log.write('%s %s API limit exceeded Sleeping with book_id:%s\n' %(datetime.now(), __worker_name, book_id))
                log.flush()
                time.sleep(seconds_until_google_quota_refresh())
                q_mass_worker.add(book_id)
                continue    
            elif metadata_status == 2:
                log.write("%s  %s  Not Public Domain\n" %(datetime.now(), book_id))
                log.flush()
                continue
            elif metadata_status == 0:
                pass
            else:
                log.write("%s  Metadata Error, library:%s, ID:%s, status:%s\n" %(datetime.now(), 'gb', book_id, metadata_status) )
                log.flush()
                continue
        """ 
        ia_identifier_found = ia_w.check_in_IA(ia_w.library, ia_w.Id)
        if ia_identifier_found is not False:
            ia_w.save_ia_identifier(ia_identifier_found)
            continue  
	"""
        if not os.path.isfile(ia_w.pdf_path):
            download_status = gb.download_book(ia_w.Id)
            if download_status != 0:
                log.write("%s  Download Error, library:%s, ID:%s\n" %(datetime.now(), 'gb', book_id) )
                log.flush()
                continue
        download_progress_key = ia_w.book_key + ":download_progress"
        redis_py.set(download_progress_key, 1, True)   
        try:
            upload_status = ia_w.upload_to_IA(ia_w.library, ia_w.Id)
            if str(upload_status) == "[<Response [200]>]":
                upload_progress_key = ia_w.book_key + ":upload_progress"
                redis_py.set(upload_progress_key, 1, True)
                ia_w.save_ia_identifier(ia_w.ia_identifier)
        except:
            filename = ia_w.filename
            command = "rm %s" %(filename)
            try:
                subprocess.check_call(command, shell=True)     
            except:
                log.write("%s  Command rm %s failed" %(datetime.now(), filename))
                log.flush()
            
        
def main():
    global mass_worker_key, __worker_name
    mass_worker_no = sys.argv[1] if len(sys.argv)>1 else None
    if mass_worker_no == '1' or mass_worker_no == None:
        mass_worker_key = keys.redis_key4 + ":mass_worker"
        __worker_name = "Mass Worker #1"
    elif mass_worker_no == '2':
        mass_worker_key = keys.redis_key4 + ":mass_worker_2"
        __worker_name = "Mass Worker #2"
    elif mass_worker_no == '3':
        mass_worker_key = keys.redis_key4 + ":mass_worker_3"
        __worker_name = "Mass Worker #3"        
    log.write("%s  Started %s\n" %(datetime.now(), __worker_name) )
    log.flush()
    redis_key4 = keys.redis_key4 
    q_mass_worker = QueueHandler(mass_worker_key)
    if mass_worker_no == '1' or mass_worker_no == None:
        q_bulk_order = QueueHandler(redis_key4)  
        p = Process(target = wait_and_add_to_queue, args=(q_bulk_order,))      #Process spawn
        p.start()
    manager(q_mass_worker)            
        
        
if __name__ == '__main__':
    sys.exit(main())
        
