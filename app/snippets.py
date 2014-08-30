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


from xml.sax.saxutils import escape


def html_escape(text):
    """Html (" ' < >) escaping"""
    html_escape_table = {
      '"': "&quot;",
      "'": "&apos;"
    }
    return escape(text, html_escape_table)
    
    
def error_msg(error_no, book = None, email = None):
    """Return error message according to error number"""
    if error_no == 1:
        text = "Whoops! Book ID/URL: <B>%s</B> for %s is invalid !<br>Recheck it." %( book.Id, book.lib_name )
    elif error_no == 2:
        text = "Sorry! Book for the ID/URL: <B>%s</B> is not public-domain !<br>Try another book." %( book.Id )
    elif error_no == 3:
        text = ""
    elif error_no == 4:
        text = "Hmm! Invalid Library <B>%s</B> !<br>Are you using library names or values?" % book.library_id
    elif error_no == 5:
        text = "Uh Oh! Something's wrong with the Email Address: <B>%s</B> !<br>Recheck the part after '@'" % book.email
    elif error_no == 6:
        text = "Sorry, session expired or Cookies are disabled.<br>Please try again."
    elif error_no == 7:
        text = "Sorry, daily limit for selected library exceeded.<br>Please try again tomorrow."
    elif error_no == 8:
        text = "Sorry, this library does not support the general DSpace standards."
    elif error_no == 9:
        text = "Oh snap! This book is Google-digitized. Hathitrust does not allow download of Google-books through their servers.<br>But dont worry, you may search for this book on <a href = 'http://books.google.com/'>Google-books</a> and enter that ID/URL, with Google-Books as selected library."
    elif error_no == 10:
        text = "Lost! Unknown Error. Please try another ID/URL, or try after some time."
    elif error_no == 50:
        text = "Thank you Captain!<br>Your request is already being processed."
    elif error_no == 100:
        if email not in (None, ""):
            text = "Thank you Captain!<br>Your request is being processed. It only takes few minutes." +\
            " You will be informed at <a class=\"alert-link\">" + email + "</a> as soon as the upload is ready."
        else:
            text = "Thank you Captain!<br>Your request is being processed. It only takes few minutes."
    elif error_no == 500:
        text = "Wrong Password!<br>Try again."
    if error_no == 50 or error_no == 100:
        return dict(text = text, error = False)
    else:
        return dict(text = text, error = True)
        
