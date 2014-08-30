#!./flask/bin/python
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


import htmlmin
import cssmin


def minify(text, css = True, html = True, remove_comments = True):
    """Minify html and css part of text"""
    if html:
        text = htmlmin.minify( text, remove_comments = remove_comments)
        if css:
            text = cssmin.cssmin( text )
        return text
    if cssmin:
        text = cssmin.cssmin( text )
        return text
