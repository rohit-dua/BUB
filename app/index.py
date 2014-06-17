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
import cgi
import Cookie
import os
import hashlib
import json

sys.path.append('../lib')
from bottle import template
import htmlmin

import bridge
from minify import minify
import redis_py
import mysql_py


class content_head(object):
    def __new__(cls):
        return "Content-type:text/html\r\n\r\n"
        
        
def submit_job(uuid_hash, data):
    json_data = open('../../settings.json')
    settings = json.load(json_data)
    Redis_Key = settings['redis']['key_1']
    Lock_Key = settings['lock']['key_1']
    q = redis_py.Queue(Redis_Key)
    redis = redis_py.Redis()
    Redis_Key = settings['redis']['key_3']
    email = data[0] 
    sno = data[1]
    commonsName = data[2]
    md5_book = data[3]
    Id = data[4]
    library = data[5]    
    list_name = "%s:%s:%s" %(Redis_Key, library, Id)
    Lock = redis_py.Lock(Lock_Key)
    locked = False
    if redis.exists(list_name):
         locked = Lock.acquire(timeout = 60)
    redis.rpush(list_name, """{"request":{"SNO":"%s","EMAIL":"%s","COMMONSNAME":"%s"}}""" %(sno, email, commonsName) )
    db = mysql_py.db()
    redundancy_book = db.execute("SELECT COUNT(*) FROM REQUESTS WHERE MD5_BOOK='%s' AND CONFIRMED=1 AND JOB_SUBMITTED=1;",md5_book)
    if redundancy_book[0] == 0:
        q.add(sno)
    db.execute("UPDATE REQUESTS SET JOB_SUBMITTED = 1 WHERE SNO =%s;",sno)
    if locked == True:
        Lock.release()   
    db.close()     


def error_msg(error_no, book=None, email=None):
    """Return error message according to number"""
    if error_no == 1:
        text = "Whoops! Book ID/URL: <B>%s</B> for %s is invalid !<br>Recheck it." %( book.Id, book.lib_name )
    elif error_no == 2:
        text = "Sorry! Book for the ID/URL: <B>%s</B> is not public-domain !<br>Try another book." %( book.Id )
    elif error_no == 3:
        text = "Oh snap! A file with the name <B>%s</B> already exist on Commons !<br>Try another name." % book.commonsName
    elif error_no == 4:
        text = "Hmm! Invalid Library <B>%s</B> !<br>Are you using library names or values?" % book.library_id
    elif error_no == 5:
        text = "Uh Oh! Something's wrong with the Email Address: <B>%s</B> !<br>Recheck the part after '@'" % book.email
    elif error_no == 6:
        text = "Sorry, session expired or Cookies are disabled.<br>Please try again."
    elif error_no == 10:
        text = "Lost! Unknown Error. Please try another ID/URL, or try after some time."
    elif error_no == 50:   #redundancy
        return "<div class=\"alert alert-success\"><span class=\"glyphicon glyphicon-thumbs-up\"></span> Thank you Captain!<br>" +\
        "Your request is already being processed.</div>"
    elif error_no == 100:   #success
        return "<div class=\"alert alert-success\"><span class=\"glyphicon glyphicon-thumbs-up\"></span> Thank you Captain!<br>" +\
        "Your request is being processed. It only takes few minutes. You will be informed at <a class=\"alert-link\">" + email + "</a> as soon as the upload is ready." + "</div>"
    return "<div class=\"alert alert-danger\"><span class=\"glyphicon glyphicon-remove\"></span> " + text + "</div>"
    


def display(status_no, book = None, email = None):
    """Display input web page (with/without errors)"""
    head = open('templates/head.html', 'r')
    head_data = minify( head.read() )
    head.close()
    body1 = open('templates/body1.html', 'r')
    body1_data = htmlmin.minify( body1.read(), remove_comments = True)
    body1.close()
    if status_no == 0:
        print content_head() + head_data.encode('utf-8') +\
        template( body1_data, _errorNo = None, _id = None, _commonsName = None, _email = None ).encode('utf-8')        
    elif status_no != 100 and status_no != 50 and status_no != 6:       #if not success
        print content_head() + head_data.encode('utf-8') + error_msg(status_no, book).encode('utf-8') +\
        template( body1_data, _errorNo = status_no, _id = book.Id, _commonsName = book.commonsName, _email = book.email ).encode('utf-8')
    else:
        print content_head() + head_data.encode('utf-8') + error_msg(status_no, email=email).encode('utf-8') +\
        template( body1_data, _errorNo = None, _id = None, _commonsName = None, _email = None ).encode('utf-8')

        
def set_cookie():
    """Generate and set cookie containing 32 bits of entropy."""
    uuid = os.urandom(32).encode("hex")
    cookie = Cookie.SimpleCookie()
    cookie['bub_session'] = uuid
    #cookie['bub_session']["path"] = '/cgi-bin/BUB_raw/BUB/'     #path to BUB folder(change in tool-labs)
    cookie['bub_session']["httponly"] = 'httponly'
    #cookie['bub_session']["domain"] = ".app.localhost"
    print cookie.output()
    return uuid


def store_db(book, uuid):
    """Store uuid(hash value) and other parameters to DB"""
    uuid_hash = hashlib.md5(uuid).hexdigest()
    md5_sum = hashlib.md5(book.Id + book.library_id + book.email).hexdigest()
    md5_book = hashlib.md5(book.Id + book.library_id).hexdigest()
    db = mysql_py.db()
    redundancy = db.execute("SELECT COUNT(*) FROM REQUESTS WHERE MD5_SUM='%s' AND CONFIRMED=1;",md5_sum)
    if redundancy[0] != 0:
        display(status_no = 50, email=book.email)
        return 1
    command = "INSERT INTO REQUESTS (" +\
    "ID, LIBRARY, COMMONSNAME, EMAIL, MD5_SUM, MD5_BOOK, UUID_HASH)" + \
    " VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s')"
    db.execute(command, book.Id, book.library_id, book.commonsName, book.email, md5_sum, md5_book, uuid_hash)
    db.close()


def confirmation_page(book, info):
    """Display confirmation web page"""
    head = open('templates/head.html', 'r')
    head_data = minify( head.read() )
    head.close()
    body2 = open('templates/body2.html', 'r')
    body2_data = htmlmin.minify( body2.read(), remove_comments = True)
    body2.close()
    body2_data = template(body2_data,\
     _infolink = info['infoLink'],\
     _imageurl = info['image_url'],\
     _title = cgi.escape(info['title']),\
     _author = cgi.escape(info['author']),\
     _publisher = cgi.escape(info['publisher']),\
     _publishedDate = cgi.escape(info['publishedDate']),\
     _description = cgi.escape(info['description']),\
     _accessViewStatus = info['accessViewStatus'])
    uuid = set_cookie()
    status = store_db(book, uuid)
    if status == 1:
        return 1
    print content_head() + head_data.encode('utf-8') + body2_data.encode('utf-8').decode('utf-8', 'replace').encode('utf-8')

        

def manager():
    form = cgi.FieldStorage()
    if (form.has_key("library") and form.has_key("Id") and form.has_key("commonsName") and form.has_key("email")):
        library_id = cgi.escape(form["library"].value[:40])
        Id = cgi.escape(form["Id"].value[:150])
        commonsName = cgi.escape(form["commonsName"].value[:40])
        email = cgi.escape(form["email"].value[:40])
        book = bridge.fields(library_id, Id, commonsName, email)
        fields_status = book.verify_fields()
        if fields_status != 0:
            display(fields_status, book)
            return 0   
        else:
            confirmation_page(book, bridge.book_info(library_id, Id))
            return 0                
    elif (form.has_key("upload")):
        if cgi.escape(form["upload"].value[:10]) == 'confirm':
            if 'HTTP_COOKIE' in os.environ:      
                cookie_string=os.environ.get('HTTP_COOKIE')
                if not cookie_string:
                    display(status_no = 0)
                    return 0
                c = Cookie.SimpleCookie()
                c.load(cookie_string)
                try:    
                    uuid = c['bub_session'].value
                    uuid_hash = hashlib.md5(uuid).hexdigest()
                except KeyError:
                    display(status_no = 0)
                    return 0
                db = mysql_py.db()
                command = "UPDATE REQUESTS SET CONFIRMED = 1 WHERE UUID_HASH = '%s';"
                try:
                    db.execute(command, uuid_hash)
                except:
                    display(status_no = 6)
                    db.close()
                    return 1
                command = "SELECT EMAIL, SNO, COMMONSNAME, MD5_BOOK, ID, LIBRARY FROM REQUESTS WHERE UUID_HASH='%s';"
                try:
                    data = db.execute(command, uuid_hash)
                    email = data[0] 
                    sno = data[1]
                    commonsName = data[2]
                    md5_book = data[3]
                    Id = data[4]
                    library = data[5]
                    db.close()
                except:
                    display(status_no = 6)
                    db.close()
                    return 1     
                display(status_no = 100, email = email)
                submit_job(uuid_hash, data)
                return 0
            else:
                display(status_no = 0)
                return 0
        else: 
            display(status_no = 0)
            return 0
    else: 
        display(status_no = 0)
        return 0



        
        
def main():
    manager()
    



if __name__ == '__main__':
    sys.exit(main())


