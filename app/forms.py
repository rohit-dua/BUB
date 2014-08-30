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


from flask.ext.wtf import Form
from wtforms import TextField, validators, ValidationError
from flask.ext.wtf import RecaptchaField


def confirm(form,field):
    if field.data != 'confirm':
        raise ValidationError('Field must be less than 50 characters')


class UploadForm(Form):
    library_id = TextField('library', [validators.Length(min=2, max=40), validators.Required()])
    book_id = TextField('book_id', [validators.Length(min=2, max=150), validators.Required()])
    email = TextField('email', [validators.Length(min=0, max=100)])
    
    
class ConfirmForm(Form):
    upload = TextField('upload', [validators.Required(), confirm])

    
class AdminLogin(Form):
    password = TextField('password', [validators.Length(min=2, max=30), validators.Required()])
    recaptcha = RecaptchaField()

    
class MassUpload(Form):
    ids = TextField('ids', [validators.Required()])
    language = TextField('language', [validators.Length(min=0, max=100)])
    email = TextField('email', [validators.Length(min=0, max=100)])

    
class ReUpload(Form):
    recaptcha = RecaptchaField()    
    email = TextField('email', [validators.Length(min=0, max=100)])
    key = TextField('key', [validators.Length(min=0, max=100)])


class WildcardForm(Form):
    link_type = TextField('link_type', [validators.Length(min=2, max=40), validators.Required()])
    book_url = TextField('book_url', [validators.Length(min=0, max=150)])
    book_pdf_url = TextField('book_pdf_url', [validators.Length(min=0, max=150)])
    from_no = TextField('from_no', [validators.Length(min=0, max=20)])
    to_no = TextField('to_no', [validators.Length(min=0, max=20)])
    email = TextField('email', [validators.Length(min=0, max=100)])
    title = TextField('title', [validators.Length(min=0, max=330), validators.Required()])
    author = TextField('author', [validators.Length(min=0, max=300)])
    publisher = TextField('publisher', [validators.Length(min=0, max=300)])
    date = TextField('date', [validators.Length(min=0, max=100)])
    desc = TextField('desc', [validators.Length(min=0, max=1000)])
    language = TextField('language', [validators.Length(min=0, max=100), validators.Required()])
     
