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


from app import db
from datetime import datetime

class Request(db.Model):
    sno = db.Column(db.Integer, primary_key = True)
    book_id = db.Column(db.String(150), nullable=False)
    library = db.Column(db.String(40), nullable=False)
    email = db.Column(db.String(40), nullable=True)
    confirmed = db.Column(db.Integer, default = 0)
    job_submitted = db.Column(db.Integer, default = None)
    md5_request = db.Column(db.String(100), nullable=False)
    md5_book = db.Column(db.String(100), nullable=False)
    md5_uuid = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


class Book(db.Model):
    sno = db.Column(db.Integer, primary_key = True)
    book_id = db.Column(db.String(150), nullable=False)
    library = db.Column(db.String(40), nullable=False)
    md5_book = db.Column(db.String(100))
    connected_request_sno = db.Column(db.String(255))
    library_url = db.Column(db.String(150))
    meta_data = db.Column(db.String(65535))
    output_file = db.Column(db.String(100))
    language = db.Column(db.String(40))
    ia_response = db.Column(db.String(11))
    download_progress = db.Column(db.Integer)
    upload_progress = db.Column(db.Integer)
    email_progress = db.Column(db.Integer)
    ocr_progress = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    requests = db.Column(db.String(255))

