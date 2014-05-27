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
       
sys.path.append('../lib')
import htmlmin       

from minify import minify
            
            
CONTENT_HEAD = "Content-type:text/html\r\n\r\n"
        
        
def main():
    """Display 'About BUB' web page"""
    head = open('templates/head.html', 'r')
    head_data = minify( head.read() )
    head.close()
    about = open('templates/about_body.html', 'r')
    about_data = htmlmin.minify( about.read(), remove_comments = True)
    about.close()  
    print CONTENT_HEAD + head_data.encode('utf-8') + about_data.encode('utf-8').decode('utf-8', 'replace').encode('utf-8')
    sys.exit(0)
    
if __name__ == '__main__':
    sys.exit(main())
