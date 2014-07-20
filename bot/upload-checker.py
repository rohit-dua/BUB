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

import json
import re
import MySQLdb
import time
import smtplib
import sys
import requests
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from subprocess import Popen, PIPE

sys.path.append('../lib')
import redis_py
import mysql_py
import keys


def remove_from_db(users_request):
    """Remove database entry of request."""
    db = mysql_py.Db()
    for u in users_request:
        info = json.loads(u)
        sno = int(info['sno'])
        command = "DELETE FROM REQUESTS WHERE SNO = %s;"
        db.execute(command, sno)
    db.close() 
        
def send_email(users_request, ia_identifier):
    """send html email to all requests associated with
    a book."""
    subject = "Your upload is ready!"
    for u in users_request:
        try:
            info = json.loads(u)
        except:
            continue
        email = info['email']
        if email in (None, ""):
            continue
        commons_name = info['commons_name']
        commons_upload_link = "http://tools.wmflabs.org/ia-upload/commons/fill?iaId=%s&commonsName=%s" %(ia_identifier, commons_name)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = "tools.bub@tools.wmflabs.org"
        msg['To'] = email
        text = """Hi!\n\nYour upload is ready in Internet-archive!\nhttp://archive.org/details/%s\n\nHere is the link to upload the book to commons:\n%s
        \n\n--\n*** This is an automatically generated email, please do not reply ***\nhttp://tools.wmflabs.org/bub/""" %( ia_identifier, commons_upload_link)
        html = """\
        <html>
          <head></head>
          <body>
            <p>Hi!<br><br>
               Your <a href ='http://archive.org/details/%s'>upload</a> is ready in Internet-archive!<br><br>
               <a href='%s'>Click here</a> to upload the book to commons.
            </p>
            <br>
            <p style="font-size:small;-webkit-text-size-adjust:none;color:#666;">%s<br>&mdash;<br>
            This is an automatically generated email, please do not reply.<br>                     
            <a href='http://tools.wmflabs.org/bub/'>BUB : Book Uploader Bot</a></p>
          </body>
        </html>
        """ %( ia_identifier, commons_upload_link, os.urandom(8).encode("hex"))
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        p = Popen(["/usr/sbin/exim", "-odf", "-i", email], stdin=PIPE)
        p.communicate(msg.as_string())
	#logger.info( "mail sent to:%s" %email)
            

def check_if_upload_ready():
    #global DB
    #DB = mysql_py.db()
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
            ia_identifier = redis.get(book_key + ":ia_identifier")

            uploaded = 0
            r = requests.get('http://archive.org/metadata/%s' %(ia_identifier) ).json()
            if 'metadata' in r.keys():
                if 'ocr' in r['metadata'].keys():
                    if r['metadata']['ocr'] == 'language not currently OCRable':
                        uploaded = 2
            if 'DjVuTXT' in str(r):
                uploaded = 1
            if uploaded != 0:
                Lock.acquire(timeout = 60*2)
                users_request = redis.smembers(book_key + ":requests")
                redis.delete( book_key + ":requests")
                remove_from_db(users_request)
                Lock.release()
                q.remove(book_key)
                send_email( users_request, ia_identifier )  
                OCR_progress_key = book_key + ":OCR_progress"
                redis.set(OCR_progress_key, 1)              
            else:
                continue
        time.sleep(2)

        
    
def main():
    check_if_upload_ready()


if __name__ == '__main__':
    main()

