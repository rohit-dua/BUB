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

#DB = object

def remove_from_db(users_info):
    """Remove database entry of request."""
    db = mysql_py.db()
    for u in users_info:
        info = json.loads(u)
        sno = int(info['request']['SNO'])
        command = "DELETE FROM REQUESTS WHERE SNO = %s;"
        db.execute(command, sno)
    db.close() 
        
def send_email(users_info, ia_identifier):
    """send html email to all requests associated with
    a book."""
    subject = "Your upload is ready!"
    for u in users_info:
        try:
            info = json.loads(u)
        except:
            continue
        email = info['request']['EMAIL']
        commonsName = info['request']['COMMONSNAME']
        commons_upload_link = "http://tools.wmflabs.org/ia-upload/commons/fill?iaId=%s&commonsName=%s" %(ia_identifier, commonsName)
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
    json_data = open('../../settings.json')
    settings = json.load(json_data)
    Redis_Key = settings['redis']['key_2']
    Lock_Key = settings['lock']['key_1']
    q = redis_py.Queue(Redis_Key)
    Lock = redis_py.Lock(Lock_Key)
    while True:
        list_names = q.pop(-1)
	if list_names is False:
	    time.sleep(2)
	    continue
        for list_name in list_names:
            ia_identifier = redis.lrange(list_name, 0, 0)[0]       
	    r = requests.head('http://archive.org/stream/%s/%s.djvu' %(ia_identifier, ia_identifier[4:]) )
            if 'content-type' in r.headers.keys():
                if r.headers['content-type'] == 'image/x.djvu':
		    #logger.info("upload completed for :%s" %ia_identifier)
                    Lock.acquire(timeout = 60*2)
                    users_info = redis.lrange(list_name, 1, -1)
                    redis.delete( list_name )
		    #try:
                    remove_from_db(users_info)
		    #except:
                    pass
                    Lock.release()
                    q.remove(list_name)
                    send_email( users_info, ia_identifier )
            else:
                continue 
        time.sleep(2)    
        
    
def main():
    check_if_upload_ready()


if __name__ == '__main__':
    main()

