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


from flask import flash, redirect, url_for, Markup, request, make_response, abort, session
from flask import render_template as rt
from app import app, db, models
from forms import UploadForm, ConfirmForm, AdminLogin, MassUpload, ReUpload, WildcardForm
from snippets import html_escape, error_msg
from os import urandom
import hashlib
import json
import re
import sys
from functools import wraps

from datetime import datetime, timedelta
from validate_email import validate_email
from internetarchive import get_item
from tld import get_tld
 
from utils import redis_py, keys, mysql_py
from utils.minify import minify
import bridge

sys.path.append('./utils')
sys.path.append('../utils')
from minify import minify
from retry import retry, ia_online


d = mysql_py.Db()

libraries = [
        dict(
            value = 'gb',
            name = 'Google-Books'
        ),
        dict(
            value = 'br',
            name = 'Brasiliana-USP'
        ),
        dict(
            value = 'usp',
            name = 'DSpace-based-library'
        ),
        dict(
            value = 'ht',
            name = 'HathiTrust'
        ),
        dict(
            value = 'mdc',
            name = 'Digital-Memory-of-Catalonia(mdc)' 
        ),
	dict(
            value = 'gal',
	    name = 'Gallica'
	),
        dict(
            value = '/bub/manual/',
            name = 'Manual-Wildcard'
        )
]


def render_template(text, **kwargs):
    return minify(rt(text, **kwargs), css = False)

def reset_book_progress(library, ia_identifier):
    r= redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, library, ia_identifier)
    download_progress_key = book_key + ":download_progress"
    upload_progress_key = book_key + ":upload_progress"
    ia_response_key = book_key + ":ia_response"
    OCR_progress_key = book_key + ":OCR_progress"
    email_progress_key = book_key + ":email_progress"
    r.delete(download_progress_key)
    r.delete(upload_progress_key)
    r.delete(ia_response_key)
    r.delete(OCR_progress_key)
    r.delete(email_progress_key)
    d.execute("delete from book where email_progress=1 and library=%s and book_id=%s;", library, ia_identifier)


def store_request(book, uuid):
    """Store uuid(hash value) and other parameters to Db"""
    md5_uuid = hashlib.md5(uuid).hexdigest()
    md5_request = hashlib.md5(book.Id + book.library_id + book.email).hexdigest()
    md5_book = hashlib.md5(book.Id + book.library_id).hexdigest()
    request = models.Request(book_id = book.Id, library = book.library_id, email = book.email, md5_request = md5_request, md5_book = md5_book, md5_uuid = md5_uuid)
    db.session.add(request)
    db.session.commit()
    

def redundant_request(book):
    """Check if similar request already exists in the database."""
    md5_request = hashlib.md5(book.Id + book.library_id + book.email).hexdigest()
    result = models.Request.query.filter_by(md5_request=md5_request,confirmed=1).first()
    if result == None:
        return False
    else:
        return True


def submit_job(stored_request):
    """Add book-request to the job queues"""
    redis_key1 = keys.redis_key1
    lock_key1 = keys.lock_key1
    q = redis_py.Queue(redis_key1)
    q_global_job = redis_py.Queue(redis_key1+"global")
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, stored_request.library, stored_request.book_id)
    book_request_key = book_key + ":requests"
    Lock = redis_py.Lock(lock_key1)
    locked = False
    if redis.exists(book_request_key):
        locked = Lock.acquire(timeout = 60)          
    request = dict(sno = stored_request.sno, email = stored_request.email)
    redis_py.sadd(book_request_key, json.dumps(request),request_cache= True)
    redundant_request = models.Request.query.filter_by(md5_book=stored_request.md5_book,confirmed=1,job_submitted=1).first()
    if redundant_request == None:
	reset_book_progress(stored_request.library, stored_request.book_id)
        md5_book = hashlib.md5(stored_request.book_id + stored_request.library).hexdigest()
        library_url_key = book_key + ":library_url"
        library_url = redis_py.get(library_url_key, True)
        metadata_key = book_key + ":meta_data"
        meta_data = redis_py.get(metadata_key, True)
        book = models.Book(book_id=stored_request.book_id, library=stored_request.library, 
            md5_book=stored_request.md5_book, connected_request_sno=stored_request.sno, requests=json.dumps(request),
            library_url=library_url, meta_data=meta_data)
        db.session.add(book)
	#db.session.commit()        
	q.add(stored_request.sno)
        stored_request.job_submitted = 1
	db.session.commit()
        q_global_job.add(json.dumps(dict(library = stored_request.library, book_id = stored_request.book_id)))
    if locked == True:
        Lock.release()   
    

def store_book_metadata(library_id, book_id, sno):
    """Store books metadata for caching purposes"""
    redis = redis_py.Redis()
    book_metadata = bridge.book_info(library_id, book_id)
    redis_key3 = keys.redis_key3
    book_key = "%s:%s:%s" %(redis_key3, library_id, book_id)
    metadata_key = book_key + ":meta_data"
    sno_key = book_key + ":sno"
    redis_py.set(metadata_key, json.dumps(book_metadata), True )
    redis_py.set(sno_key, json.dumps(sno), True )
    library_url_key = book_key + ":library_url"
    redis.expire(library_url_key, 60*60*60)


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    subtitle = "Transfer books to Internet Archive"
    form = UploadForm(request.form)
    if request.method == 'POST':
        if form.validate():
            book_id = html_escape(form.book_id.data)
            email = html_escape(form.email.data) if form.email.data not in (None,"") else ""
            book = bridge.fields(form.library_id.data, book_id, email)
            book_id = book.Id if book.Id not in (None, "") else book_id
            redis = redis_py.Redis()
            redis_key3 = keys.redis_key3
            book_key = "%s:%s:%s" %(redis_key3, form.library_id.data, book_id)
            library_url_key = book_key + ":library_url"
            redis_py.set(library_url_key, form.book_id.data, True)
            redis.expire(library_url_key, 60*15)
            verification_status_no = book.verify_fields()
            if verification_status_no != 0:
                flash( error_msg(verification_status_no, book) )
                return render_template("index.html", subtitle = subtitle, libraries = libraries, form = form)
            else:
                if redundant_request(book) == True:
                    flash( error_msg(50) )
                    return render_template("index.html", subtitle = subtitle, libraries = libraries, form = form)
                book_info = bridge.book_info(form.library_id.data, book_id)  
                if isinstance(book_info, (int, long, float, complex)):
                    flash( error_msg(book_info))
                    return render_template("index.html", subtitle = subtitle, libraries = libraries, form = form)
                confirm_resp = make_response(minify(render_template("confirm.html", book_info = book_info, form = form)))
                uuid = urandom(32).encode("hex")
                confirm_resp.set_cookie('bub_session', uuid)
                store_request(book, uuid)
                return confirm_resp
        return render_template("index.html", subtitle = subtitle, libraries = libraries, form = form)
    else:
        return render_template("index.html", subtitle = subtitle, libraries = libraries, form = form)
       
       
@app.route('/confirm', methods=['POST'])
@app.route('/index/confirm', methods=['POST'])
def confirm():
    subtitle = "Transfer books to Internet Archive"
    form = ConfirmForm(request.form)
    if form.validate():
        uuid = request.cookies.get('bub_session')
        if uuid == None:
            flash( error_msg(6) )
            return redirect('/')
        md5_uuid = hashlib.md5(uuid).hexdigest()
        stored_request = models.Request.query.filter_by(md5_uuid = md5_uuid).first()
        if stored_request == None:
            flash( error_msg(6) )
            return redirect('/')
        stored_request.confirmed = 1
        db.session.commit()
        redundant_book = models.Request.query.filter_by(md5_book=stored_request.md5_book,confirmed=1,job_submitted=1).first()
        if redundant_book == None:
            store_book_metadata(stored_request.library, stored_request.book_id, stored_request.sno)
        submit_job(stored_request)
        flash( error_msg(100, email=stored_request.email) )
        return redirect( url_for('progress', subtitle = subtitle, book_id = "%s:%s"%(stored_request.library, stored_request.book_id)) )
    else:
        return redirect('/')


def extract_base_domain(url):
    """Extract and return the base domain name from the url."""
    tld = get_tld(url)
    u = re.search('.+%s' %tld, url)
    if u:
        return u.group()
    else:
        return ""


@app.route('/manual/', methods=['GET', 'POST'])
@app.route('/index/manual/', methods=['GET', 'POST'])
def manual():
    subtitle = "Upload using wildcards"
    try:
        form = WildcardForm(request.form)
    except UnboundLocalError:
        form = WildcardForm()
        return render_template("wildcard.html", subtitle = subtitle, form = form)
    if request.method == 'POST':
        if form.validate():
            if form.book_url.data in (None , "") and form.book_pdf_url.data in (None, ""):
                return render_template("wildcard.html", subtitle = subtitle, form = form)
            if form.link_type.data == 'wildcard':
                book_url = form.book_url.data if form.book_url.data not in (None,  "") else ""
                from_no = html_escape(form.from_no.data) if form.from_no.data not in (None,  "") else ""
                to_no = html_escape(form.to_no.data) if form.to_no.data not in (None,  "") else ""
                info_url = re.sub('\(\*\)', str(from_no), book_url)
                book_url = book_url + ":" + str(from_no) + "," +str(to_no)
                book_url = book_url + ":" + 'wildcard'
            elif form.link_type.data == 'pdf':
                book_url = form.book_pdf_url.data if form.book_pdf_url.data not in (None,  "") else ""
                info_url = book_url
                book_url = book_url + ":" + 'pdf'               
            library = 'man'
            Id = hashlib.md5(book_url).hexdigest()
            email = html_escape(form.email.data) if form.email.data not in (None,"") else "" 
            book = bridge.fields(library, book_url, email)
            verification_status_no = book.verify_fields()
            if verification_status_no != 0:
                flash( error_msg(verification_status_no, book) )
                return render_template("wildcard.html", subtitle = subtitle, form = form)                           
            tld = extract_base_domain(book_url)
            book_metadata = dict(    
                image_url = "",
                thumbnail_url = "",
                printType = "BOOK",
                subtitle = "",
                infoLink = info_url,
                publicDomain = True,
                scanner = tld,
                sponser = tld,               
                title = form.title.data if form.title.data not in (None,"") else "",
                author = form.author.data if form.author.data not in (None,"") else "",
                publisher = form.publisher.data if form.publisher.data not in (None,"") else "",
                publishedDate = form.date.data if form.date.data not in (None,"") else "",
                description = form.desc.data if form.desc.data not in (None,"") else "",
                language = form.language.data if form.language.data not in (None,"") else ""
            )            
            ia_identifier_suffix = get_valid_identifier_suffix(library, Id)
            redis = redis_py.Redis()
            redis_key3 = keys.redis_key3
            redis_key1 = keys.redis_key1
            book_key = "%s:%s:%s" %(redis_key3, library, ia_identifier_suffix)
            metadata_key = book_key + ":meta_data"
            redis_py.set(metadata_key, json.dumps(book_metadata), True )           
            book_request_key = book_key + ":requests"  
            request_details = dict(email = email)
            redis_py.sadd(book_request_key, json.dumps(request_details), request_cache=True)
            md5_book = hashlib.md5(ia_identifier_suffix + library).hexdigest()
	    meta_data = json.dumps(book_metadata)
            book = models.Book(book_id=ia_identifier_suffix, library=library, 
	    	requests=json.dumps(request_details), meta_data=meta_data, md5_book=md5_book)
            db.session.add(book)
            db.session.commit()
            q_global_job = redis_py.Queue(redis_key1+"global")        
            q_global_job.add(json.dumps(dict(library = library, book_id = ia_identifier_suffix)))
            q = redis_py.Queue(redis_key1)
            q.add(json.dumps(dict(library = library, Id = book_url, ia_identifier_suffix = ia_identifier_suffix)))
            flash( error_msg(100, email=email) )
            return redirect( url_for('progress', book_id = library + ":" +ia_identifier_suffix) )               
        else:
            return render_template("wildcard.html", subtitle = subtitle, form = form)
    else:
        return render_template("wildcard.html", subtitle = subtitle, form = form)
        
    

@app.route('/about/', methods=['GET', 'POST'])
def about():
    subtitle = "Transfer books directly from libraries like Google-books to Internet Archive"
    return render_template("about.html", subtitle = subtitle, libraries = libraries)
    

@app.route('/license/', methods=['GET', 'POST'])
def license():
    return redirect(url_for('static', filename='license.txt'))
    
    
def percent_complete(ia_response, download_progress, upload_progress, OCR_progress):
    if ia_response == None:
        return 0
    per = 1
    per = (per + download_progress) if download_progress != None else per
    per = (per + upload_progress) if upload_progress != None else per
    per = (per + OCR_progress) if OCR_progress != None else per
    return (per/4.0)*100.0
    

def auto_refresh_time(ia_response):
    if ia_response == None:
        return 30
    if ia_response == 1:
        return None
    if ia_response == 0 or ia_response == 3:
        return 10


@app.route('/progress/<book_id>/')
def progress(book_id):
    redis = redis_py.Redis()
    redis_key3 = keys.redis_key3
    redis_key1 = keys.redis_key1
    q_global_job = redis_py.Queue(redis_key1+"global")
    book_key = "%s:%s" %(redis_key3, book_id)
    library = book_id.split(':')[0]
    metadata_key = book_key + ":meta_data"
    metadata = redis_py.get(metadata_key, True)
    if metadata == None:
        abort(404)
    metadata = json.loads(metadata)
    if metadata['title']:
        if len(metadata['title']) > 70:
            subtitle =  metadata['title'][:65] + ".."
        else:
            subtitle = metadata['title']
    progress = dict()
    ia_response_key = book_key + ":ia_response"
    ia_response = redis_py.get(ia_response_key, True)
    ia_response = int(ia_response) if ia_response else None
    progress.update( dict(ia_response = ia_response))
    download_progress_key = book_key + ":download_progress"
    download_progress = redis_py.get(download_progress_key, True) if ia_response == 0 or ia_response == 3 else None
    download_progress = int(download_progress) if download_progress else None
    progress.update( dict(download_progress = download_progress))
    upload_progress_key = book_key + ":upload_progress"
    upload_progress = redis_py.get(upload_progress_key, True) if ia_response == 0 or ia_response == 3 else None
    upload_progress = int(upload_progress) if upload_progress else None
    progress.update( dict(upload_progress = upload_progress))
    ia_identifier_key = book_key + ":ia_identifier" 
    try:
        ia_identifier = json.loads(redis_py.get(ia_identifier_key, True))
        ia_link = "http://archive.org/details/%s" %ia_identifier if ia_identifier else ""
        progress.update( dict(ia_link = ia_link))
        progress.update( dict(ia_identifier = ia_identifier))
    except ValueError:
        ia_identifier = redis_py.get(ia_identifier_key, True)
        ia_link = "http://archive.org/details/%s" %ia_identifier if ia_identifier else ""
        progress.update( dict(ia_link = ia_link))
        progress.update( dict(ia_identifier = ia_identifier))
    except:
        pass
    ia_identifier_suffix = book_id.split(':')[-1]
    OCR_progress_key = book_key + ":OCR_progress"
    OCR_progress = redis_py.get(OCR_progress_key, True) if ia_response == 0 or ia_response == 3 else None
    OCR_progress = int(OCR_progress) if OCR_progress else None
    progress.update( dict(OCR_progress = OCR_progress))
    email_progress_key = book_key + ":email_progress"
    email_progress = redis_py.get(email_progress_key, True)
    email_progress = int(email_progress) if email_progress else None
    progress.update( dict(email_progress = email_progress))
    sno_key = book_key + ":sno"
    sno = redis_py.get(sno_key, True)
    sno = int(sno) if sno else None
    global_queue_key = json.dumps(dict(library = library, book_id = ia_identifier_suffix))
    progress.update( dict(queue_index = q_global_job.index(global_queue_key)))
    progress.update( dict(percent_complete = percent_complete(ia_response, download_progress, upload_progress, OCR_progress)))
    auto_refresh = auto_refresh_time(ia_response)
    return render_template("progress.html", subtitle = subtitle, book_info = metadata, progress = progress, auto_refresh = auto_refresh, request = request, book_id = book_id)


@app.route('/progress/')
def progress_redirect():
    return redirect('queue')


@app.route('/queue/<number_of_entries>/')
@app.route('/queue/')
def queue(number_of_entries = 100):
    subtitle = "Queue for web-based upload jobs"
    redis_key1 = keys.redis_key1
    redis_key3 = keys.redis_key3
    q_global_job = redis_py.Queue(redis_key1+"global")
    redis = redis_py.Redis()
    queue = q_global_job.pop(int(number_of_entries))
    total_OCR_waiting = 0
    total_waiting_to_run = 0
    currently_running = 0
    ongoing_job_identifier = redis.get(redis_key3 + ":ongoing_job_identifier")
    if queue:
        for index,item in enumerate(queue):
            item = json.loads(item)
            queue[index] = item
            upload_progress = redis_py.get("%s:%s:%s:upload_progress" %(redis_key3, item['library'], item['book_id']), True)
            OCR_progress = redis_py.get("%s:%s:%s:OCR_progress" %(redis_key3, item['library'], item['book_id']), True)
            if upload_progress == '1' and OCR_progress != '1':
                queue[index].update(OCR_waiting = 1)
                total_OCR_waiting += 1
            else:
                total_waiting_to_run += 1
        total_waiting_to_run  = total_waiting_to_run-1 if (index+1) != total_OCR_waiting else total_waiting_to_run
        currently_running = 1 if (index+1) != total_OCR_waiting else 0 
    return render_template("queue.html", subtitle = subtitle, total_OCR_waiting = total_OCR_waiting, total_waiting_to_run = total_waiting_to_run, queue = queue, auto_refresh = 30, present_id = ongoing_job_identifier, number_of_entries = int(number_of_entries), currently_running = currently_running)

    
@app.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404


@app.route('/admin/', methods=['GET', 'POST'])
def admin():
    subtitle = "Login for administrative tasks"
    form = AdminLogin(request.form)
    if form.validate():
        if form.password.data == keys.admin_password:
	    session['timestamp'] = datetime.now()
            return redirect('/bub/admin/mass-upload')
        else:
            flash( error_msg(500) )
            return render_template('admin_login.html', form=form, _errorNo = 500)
    return render_template('admin_login.html', subtitle = subtitle, form=form)
    
def admin_check(f = None, logger =None):
      def f_deco(f):
        @wraps(f)    
        def f_retry(*args, **kwargs):
            if not session.has_key('timestamp'):
                return redirect('/bub/admin')
            elif session.has_key('timestamp'):
                if (datetime.now() - session['timestamp']) > timedelta(minutes = 15) :
                    flash( error_msg(6) )
                    return redirect('/bub/admin')           
            return f(*args, **kwargs)    
        return f_retry
      if f is None: # in this case, the decorator is called with arguments
            def decorator(f):
                return f_deco(f)
            return decorator
      # or the decorator is called without arguments
      return f_deco(f)
    

@app.route('/admin/mass-upload/', methods=['GET', 'POST'])
@admin_check
def mass_upload():
    subtitle = "Upload several books to Internet Archive"
    form = MassUpload(request.form)
    if form.validate():
        if form.email.data:
            if validate_email(form.email.data) != True:
                flash( error_msg(5) )
                session['timestamp'] = datetime.now()
                return render_template('mass_upload.html', subtitle = subtitle, form=form, _errorNo = 5)
        redis = redis_py.Redis()
        redis_key4 = keys.redis_key4
        q = redis_py.Queue(redis_key4)
        q.add(json.dumps((form.ids.data,form.email.data, form.language.data)))
        session['timestamp'] = datetime.now()
        flash( error_msg(100, email=form.email.data) )
        return render_template('mass_upload.html', subtitle = subtitle, form=form)
    return render_template('mass_upload.html', subtitle = subtitle, form=form, _errorNo=0)


@app.route('/admin/queue/<number_of_entries>/')
@app.route('/admin/queue/')
def admin_queue(number_of_entries = 100):
    subtitle = "Queue for mass upload jobs"
    redis_key4 = keys.redis_key4
    q_mass_worker = redis_py.Queue(redis_key4 + ":mass_worker")
    queue = q_mass_worker.pop(number_of_entries)
    total_waiting_to_run = 0
    if queue:
        for index,item in enumerate(queue):
            try:
                json_item = json.loads(item)
                if isinstance(json_item, list):
                    queue.remove(item)
                    continue
            except ValueError:
                pass
            total_waiting_to_run += 1 
    return render_template("queue.html", subtitle = subtitle, total_waiting_to_run = total_waiting_to_run, queue = queue, auto_refresh = 30, admin_queue = True, number_of_entries = int(number_of_entries))


@app.route('/admin/logout/', methods=['GET', 'POST'])
def admin_logout():
    if not session.has_key('timestamp'):
        return redirect('admin')
    elif session.has_key('timestamp'):
        session['timestamp'] = datetime(2000, 1, 1, 1, 1, 1, 1)
        return redirect('admin')    


@retry(tries = 2, delay = 5)
@ia_online(check_overload = False)
def get_valid_identifier_suffix(library, Id):
    item = get_item("%s_%s_%s_1" %('bub', library, Id))
    if item.exists == False:
        item = get_item("%s_%s_%s" %('bub', library, Id))
        if item.exists == False:
            return Id
    for index in range(2,10):
        item = get_item("%s_%s_%s_%s" %('bub', library, Id, index))
        if item.exists == False:
            return Id+"_"+str(index)
    item = get_item(urandom(16).encode("hex"))
    return item
 

@app.route('/progress/<book_id>/reupload/<email>/<key>', methods=['GET', 'POST'])
@app.route('/progress/<book_id>/reupload/', methods=['GET', 'POST'])
def reupload(book_id, email = "", key = ""):   
    subtitle = "Reupload book to Internet Archive"
    form = ReUpload()
    if email in (None, "") and key not in (None, ""):
        return render_template('reupload.html', subtitle = subtitle, form=form)    
    if key != hashlib.md5(str(email)+str(keys.flask_app_secret)).hexdigest() and key not in (None, ""):
        return render_template('reupload.html', subtitle = subtitle, form=form)
    form = ReUpload()
    if form.validate() or key not in (None, ""):
        book_values = re.search("(.*):(.*)", book_id)
        library = book_values.group(1)
        Id = book_values.group(2)
        ia_identifier_suffix = get_valid_identifier_suffix(library, Id)
	reset_book_progress(library, ia_identifier_suffix)
        redis = redis_py.Redis()
        redis_key3 = keys.redis_key3
        book_metadata = redis_py.get(redis_key3+":"+book_id+":meta_data", True)
        book_key = "%s:%s:%s" %(redis_key3, library, ia_identifier_suffix)
        metadata_key = book_key + ":meta_data"
        book_request_key = book_key + ":requests"
        redis_py.set(metadata_key, book_metadata, True )   
        request = dict(email = form.email.data)
        redis_py.sadd(book_request_key, json.dumps(request), request_cache=True)   
        book = models.Book(book_id=ia_identifier_suffix, library=library, requests=json.dumps(request), meta_data=book_metadata)
        db.session.add(book)
        db.session.commit()
	redis_key1 = keys.redis_key1
        q_global_job = redis_py.Queue(redis_key1+"global")        
        q_global_job.add(json.dumps(dict(library = library, book_id = ia_identifier_suffix)))
        q = redis_py.Queue(redis_key1)
        q.add(json.dumps(dict(library = library, Id = Id, ia_identifier_suffix = ia_identifier_suffix)))
        flash( error_msg(100, email=form.email.data) )
        return redirect( url_for('progress', book_id = library + ":" +ia_identifier_suffix) )  
    else:
        return render_template('reupload.html', subtitle = subtitle, form=form) 
           
