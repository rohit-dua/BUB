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


import json
import re
import MySQLdb
import time
import smtplib
import sys
#import requests  --  imported from retry (with retry wrapper))
import os
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from subprocess import Popen, PIPE
from urllib import quote_plus
from datetime import datetime

from jinja2 import Template

sys.path.append('../utils')
import redis_py
import mysql_py
import keys
from retry import retry, ia_online, requests
#from ..utils import redis_py, mysql_py, keys


log = open('upload_checker.log', 'a')
email_log = open('email.log', 'a')


def remove_from_db(users_request):
    """Remove database entry of the request."""
    db = mysql_py.Db()
    for u in users_request:
        info = json.loads(u)
        if 'sno' in info.keys():
            sno = int(info['sno'])
            command = "delete from request where sno = %s;"
            db.execute(command, sno)
    db.close() 
        
        
def send_email(users_request, ia_identifier, book_key = None):
    """Send notification email to all requests associated with
    a book."""
    for u in users_request:
        info = json.loads(u)
        email = info['email']    
        if email in (None, ""):
            continue
        msg = MIMEMultipart('alternative')
        msg['From'] = "tools.bub@tools.wmflabs.org"
        msg['To'] = email 
        html_template_data = open('./templates/email.html', 'r') 
        html_template = Template(html_template_data.read())
        if isinstance(ia_identifier, list):
            book_id = re.search('bub_([^:.]+):(.+)',book_key).group(2)
            msg['Subject'] = "Similar uploads found on IA!"  
            text = """Your upload was stopped.\nSimilar uploads were found on the internet archive\nVisit: http://tools.wmflabs.org/bub/%s\n\n--\n*** This is an automatically generated email, please do not reply ***\nhttp://tools.wmflabs.org/bub/""" %book_key   
            key = hashlib.md5(str(email)+str(keys.flask_app_secret)).hexdigest()
            reupload_link = 'http://tools.wmflabs.org/bub/progress/%s/reupload/%s/%s' %(book_id, email, key)
            html = html_template.render(ia_identifier = ia_identifier, reupload_link = reupload_link)
        else:
            msg['Subject'] = "Your upload is ready!" 
            text = """Hi!\n\nYour upload is ready in Internet-archive!\nhttp://archive.org/details/%s\n\n--\n*** This is an automatically generated email, please do not reply ***\nhttp://tools.wmflabs.org/bub/""" %ia_identifier
            random_number = os.urandom(16).encode("hex")
            html = html_template.render(ia_identifier = str(ia_identifier), random = random_number)
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        p = Popen(["/usr/sbin/exim", "-odf", "-i", email], stdin=PIPE)
        p.communicate(msg.as_string())
        if isinstance(ia_identifier, list):
            email_log.write('%s  %s  %s  IA-found\n' %(email, book_id, datetime.now()))
        else:
            email_log.write('%s  %s  %s\n' %(email, ia_identifier, datetime.now()))
        email_log.flush()
          
            
def delete_from_global_queue(book_key):
    """Delete entry from global-queue"""
    q_global_job = redis_py.Queue(keys.redis_key1+"global") 
    pattern = re.search('bub_.+:(.+):(.+)', book_key)
    library = pattern.group(1)
    book_id = pattern.group(2)
    q_global_job.remove(json.dumps( dict(library = library, book_id = book_id) ))


@ia_online(logger = log, check_overload = False)
def get_ia_metadata(ia_identifier):
    r = requests.get('http://archive.org/metadata/%s' %(ia_identifier) ).json()
    return r
        

def check_if_upload_ready():
    redis = redis_py.Redis()
    redis_key2 = keys.redis_key2
    lock_key1 = keys.lock_key1
    q = redis_py.Queue(redis_key2)
    Lock = redis_py.Lock(lock_key1)
    while True:
        book_keys = q.pop(-1)
        if book_keys is False:
            time.sleep(2)
            continue
        for book_key in book_keys:
            uploaded = 0
            ia_identifier = redis.get(book_key + ":ia_identifier")           
            ia_identifier = json.loads(ia_identifier)
            if isinstance(ia_identifier, list):
                Lock.acquire(timeout = 60*2)
                users_request = redis.smembers(book_key + ":requests")
                if users_request != None:
                    redis.delete( book_key + ":requests")
		    remove_from_db(users_request)
                Lock.release()            
                q.remove(book_key)
                if users_request != None:
                    send_email( users_request, ia_identifier, book_key = book_key )                
                email_progress_key = book_key + ":email_progress" 
                redis.set(email_progress_key, 1) 
		delete_from_global_queue(book_key)
                continue
            else:    
                r = get_ia_metadata(ia_identifier)
                if 'metadata' in r.keys():
                    if 'ocr' in r['metadata'].keys():
                        if r['metadata']['ocr'] == 'language not currently OCRable':
                            uploaded = 2
                if 'DjVuTXT' in str(r) or 'Djvu XML' in str(r):
                    uploaded = 1
                if uploaded != 0:
                    Lock.acquire(timeout = 60*2)
                    users_request = redis.smembers(book_key + ":requests")
                    if users_request != None:
                        redis.delete( book_key + ":requests")
                        remove_from_db(users_request)
                    Lock.release()
                    q.remove(book_key)
                    if users_request != None:
                        send_email( users_request, str(ia_identifier) )
                    email_progress_key = book_key + ":email_progress" 
                    redis.set(email_progress_key, 1) 
                    delete_from_global_queue(book_key)
                    OCR_progress_key = book_key + ":OCR_progress"
                    redis.set(OCR_progress_key, 1)          
                else:
                    continue
        time.sleep(2)
   
    
def main():
    log.write('%s  upload-checker.py started\n' %datetime.now())
    log.flush()
    check_if_upload_ready()


if __name__ == '__main__':
    main()

