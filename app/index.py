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
import MySQLdb
import hashlib
import time
import json

sys.path.append('../lib')
from bottle import template
import htmlmin

import bridge
from minify import minify


CONTENT_HEAD = "Content-type:text/html\r\n\r\n"
LIBRARY = ""
ID = ""
COMMONSNAME = ""
EMAIL = ""
DB_HOST = ""
DB_USERNAME = ""
DB_PASSWORD = ""
DB_DATABASE = ""


def init(error_no):
    """Display input web page (with/without errors)"""
    head = open('templates/head.html', 'r')
    head_data = minify( head.read() )
    head.close()
    body1 = open('templates/body1.html', 'r')
    body1_data = htmlmin.minify( body1.read(), remove_comments = True)
    body1.close()
    if error_no != 100 and error_no != 50:       #if not success
        print CONTENT_HEAD + head_data.encode('utf-8') + error(error_no).encode('utf-8') +\
        template( body1_data, _errorNo = error_no, _id = ID, _commonsName = COMMONSNAME, _email = EMAIL ).encode('utf-8')
    else:
        print CONTENT_HEAD + head_data.encode('utf-8') + error(error_no).encode('utf-8') +\
        template( body1_data, _errorNo = None, _id = None, _commonsName = None, _email = None ).encode('utf-8')
    sys.exit(0)
        
        
def error(error_no = 0):
    """Assign error message according to number"""
    if error_no == 0:
        return ""
    elif error_no == 1:
        text = "Whoops! Book ID/URL: <B>%s</B> for %s is invalid !<br>Recheck it." %( ID, bridge.LIBRARY_NAME )
    elif error_no == 2:
        text = "Sorry! Book for the ID/URL: <B>%s</B> is not public-domain !<br>Try another book." %( ID )
    elif error_no == 3:
        text = "Oh snap! A file with the name <B>%s</B> already exist on Commons !<br>Try another name." % COMMONSNAME
    elif error_no == 4:
        text = "Hmm! Invalid Library <B>%s</B> !<br>Are you using library names or values?" % LIBRARY
    elif error_no == 5:
        text = "Uh Oh! Something's wrong with the Email Address: <B>%s</B> !<br>Recheck the part after '@'" % EMAIL
    elif error_no == 6:
        text = "Sorry, session expired or Cookies are disabled.<br>Please try again."
    elif error_no == 10:
        text = "Lost! Unknown Error. Please try another ID/URL, or try after some time."
    elif error_no == 50:   #redundancy
        return "<div class=\"alert alert-success\"><span class=\"glyphicon glyphicon-thumbs-up\"></span> Thank you Captain!<br>" +\
        "Your request is already being processed.</div>"
    elif error_no == 100:   #success
        return "<div class=\"alert alert-success\"><span class=\"glyphicon glyphicon-thumbs-up\"></span> Thank you Captain!<br>" +\
        "Your request is being processed. You will be informed at <a class=\"alert-link\">" + EMAIL + "</a> as soon as the upload is ready." + "</div>"
    return "<div class=\"alert alert-danger\"><span class=\"glyphicon glyphicon-remove\"></span> " + text + "</div>"
    

def verify_fields():
  return bridge.verify(LIBRARY, ID, COMMONSNAME, EMAIL)

    
def set_cookie():
    """generate and set cookie containing 32 bits of entropy."""
    uuid = os.urandom(32).encode("hex")
    cookie = Cookie.SimpleCookie()
    cookie['bub_session'] = uuid
    #cookie['bub_session']["path"] = '/cgi-bin/BUB_raw/BUB/'     #path to BUB folder(change in tool-labs)
    cookie['bub_session']["httponly"] = 'httponly'
    print cookie.output()
    return uuid

def mysql(command, *args ):
    """Execute MySQL command, return result if required."""
    try:
        data = ""
        global DB_HOST, DB_USERNAME, DB_PASSWORD, DB_DATABASE
        if DB_USERNAME == '':
            json_data = open('settings.json')
            settings = json.load(json_data)
	    DB_HOST = settings['db']['host']
            DB_USERNAME = settings['db']['username']
            DB_PASSWORD = settings['db']['password']
	    DB_DATABASE = settings['db']['database']
	    json_data.close()
        db = MySQLdb.connect(DB_HOST, DB_USERNAME, DB_PASSWORD, DB_DATABASE);
        cursor = db.cursor()
        cursor.execute(command % args)
        if command[:6] != 'SELECT':
            db.commit()
        else: 
            data = cursor.fetchone()
    except: 
        db.rollback()
    finally:        
        if db:    
            db.close()
        return data


def store_db(uuid):
        """Store uuid(hash value) and other parameters to DB"""
        uuid_hash = hashlib.md5(uuid).hexdigest()
        t=time.time()
        try:
            ua = cgi.escape(os.environ["HTTP_USER_AGENT"])
        except:
            ua = 'UNKNOWN'
        md5_sum = hashlib.md5(bridge.parsed_ID + LIBRARY + EMAIL).hexdigest()
        redundancy = mysql("SELECT COUNT(*) FROM REQUESTS WHERE MD5_SUM='%s' AND CONFIRMED=1;",md5_sum)
        if redundancy[0] != 0:
            init(50)
        command = "INSERT INTO REQUESTS (" +\
        "ID, LIBRARY, COMMONSNAME, EMAIL, TIME, USER_AGENT, MD5_SUM)" + \
        " VALUES ('%s', '%s', '%s', '%s', '%s','%s', '%s')"
        mysql(command, bridge.parsed_ID, LIBRARY,COMMONSNAME,EMAIL, t, ua, md5_sum)
        command = "INSERT INTO SESSIONS (UUID_HASH) VALUES ('%s')"
        mysql(command, uuid_hash)

    
def confirmation_page(info):
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
    store_db(uuid)
    print CONTENT_HEAD + head_data.encode('utf-8') + body2_data.encode('utf-8').decode('utf-8', 'replace').encode('utf-8')
        
    
def main():
    form = cgi.FieldStorage()
    global LIBRARY, ID, COMMONSNAME, EMAIL
    if (form.has_key("library") and form.has_key("Id") and form.has_key("commonsName") and form.has_key("email")):
        LIBRARY = cgi.escape(form["library"].value[:40])
        ID = cgi.escape(form["Id"].value[:150])
        COMMONSNAME = cgi.escape(form["commonsName"].value[:40])
        EMAIL = cgi.escape(form["email"].value[:40])
        status_field = verify_fields()
        if status_field != 0:
            init(status_field)
        else:
            confirmation_page( bridge.thumbnail_info() )
    elif (form.has_key("upload")):
        if cgi.escape(form["upload"].value[:10]) == 'confirm':
            if 'HTTP_COOKIE' in os.environ:            
                cookie_string=os.environ.get('HTTP_COOKIE')
                if not cookie_string:
                    init(0)
                c = Cookie.SimpleCookie()
                c.load(cookie_string)
                try:    
                    uuid = c['bub_session'].value
                    uuid_hash = hashlib.md5(uuid).hexdigest()
                except KeyError:
                    init(0)
                #command = "SELECT EMAIL FROM REQUESTS WHERE UUID_HASH = '%s';"
                command = "SELECT REQUESTS.EMAIL FROM REQUESTS INNER JOIN SESSIONS ON"+\
                " SESSIONS.SNO=REQUESTS.SNO AND SESSIONS.UUID_HASH='%s';"
                try:
                    EMAIL  = mysql(command, uuid_hash)[0]
                except:
                    init(6)
                #command = "UPDATE REQUESTS SET CONFIRMED = 1 WHERE UUID_HASH = '%s';"
                command = "UPDATE REQUESTS JOIN SESSIONS ON SESSIONS.SNO=REQUESTS.SNO"+\
                " AND SESSIONS.UUID_HASH='%s' SET REQUESTS.CONFIRMED = 1;"
                try:
		    mysql(command, uuid_hash)
                except:
                    init(6)
                mysql("DELETE FROM SESSIONS WHERE UUID_HASH='%s';", uuid_hash)
                #push all parameters to queue
                init(100)
            else:
                init(0)
        else:
            init(0)
    else:
        init(0)
    

if __name__ == '__main__':
    sys.exit(main())

