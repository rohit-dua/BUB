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


import time
from datetime import datetime
from functools import wraps
import sys
import requests
      
      
def retry(f = None, ExceptionToCheck = None, tries=3, delay=1, backoff = 1, logger=None, stdout = False):
      """Retry decorator"""
      def f_deco(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries >= 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck, e:
                    msg = "%s, Retry in %d seconds..." % (str(e), mdelay)
                    if mtries != tries:
                        msg = "  :" + msg
                    else:
                        msg = "%s  func:%s  args:%s%s\n  :%s\n" %(str(datetime.now()), f.__name__, str(args), str(kwargs), msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
                except:
                    if ExceptionToCheck != None:
                        msg = "%s  func:%s args:%s%s  %s\n" %(datetime.now(), f.__name__, str(args), str(kwargs), str(sys.exc_info()[0]))
                        mtries = 0
                    else:
                        msg = "%s, Retry in %d seconds..." % (str(sys.exc_info()[0]), mdelay)
                        if mtries != tries:
                            msg = "  :" + msg     
                        else:
                            msg = "%s  func:%s  args:%s%s\n  :%s\n" %(str(datetime.now()), f.__name__, str(args), str(kwargs), msg)
                        time.sleep(mdelay)
                        mtries -= 1  
                        mdelay *= backoff                 
                if logger:
                    logger.write(msg)
                    logger.flush()
                    if mtries < 1:
                        logger.write("--------------------\n")
                        logger.flush()
                elif stdout:
                    print msg  
            if  ExceptionToCheck:
		if logger:
                    logger.write( str(ExceptionToCheck) + 'func:%s args:%s%s\n' %(f.__name__, str(args), str(kwargs) )) 
            else:
		if logger:
                    logger.write("ERROR: %s  func:%s args:%s%s\n" %(str(sys.exc_info()[0]), f.__name__, str(args), str(kwargs) )) 
            if logger:
                logger.flush()
        return f_retry
      if f is None: # in this case, the decorator is called with arguments
            def decorator(f):
                return f_deco(f)
            return decorator
      # or the decorator is called without arguments
      return f_deco(f)        


def wait_till_ia_online(delay = 60, once=False):
    """Check and wait until internet archive query search is active(working)"""
    r = requests.get("""http://archive.org/advancedsearch.php?q=identifier%%3Atest&[]=identifier&sort[]=&sort[]=&sort[]=&rows=10&page=1&output=json""")
    if once:
        if r.text == "":
            return False
        else:
            return True
    while r.text == "":
        time.sleep(delay)
        r = requests.get("""http://archive.org/advancedsearch.php?q=identifier%%3Atest&[]=identifier&sort[]=&sort[]=&sort[]=&rows=10&page=1&output=json""")

def wait_if_overload(delay = 5, once=False):
    S3_access_key = keys.S3_access_key
    url = 'http://s3.us.archive.org/?check_limit=1&accesskey=%s&bucket=bub' %S3_access_key 
    if once:
        r = requests.get(url)
        text = r.json()
        return text["over_limit"]
    overload = 1
    while(overload == 1):
        r = requests.get(url)
        text = r.json()
        if "over_limit" in text.keys():
            if text["over_limit"] == 0:
                overload = 0    
            else:
                time.sleep(delay)
        else:
            time.sleep(delay)
    return 0
    
    
def ia_online(f = None, delay=60, logger =None, check_overload = True):
      """Internet archive query search check decorator"""
      def f_deco(f):
        @wraps(f)    
        def f_retry(*args, **kwargs):
            ia_status = wait_till_ia_online(once = True)
            if ia_status == True:
                return f(*args, **kwargs)
            if logger:
                logger.write("%s  func:%s  args:%s%s\n" %(str(datetime.now()), f.__name__, str(args), str(kwargs) ))
                logger.write('  :Internet Archive Offline\n')
                logger.flush()
            wait_till_ia_online(delay)
            if logger:
                logger.write("%s  func:%s  args:%s%s\n" %(str(datetime.now()), f.__name__, str(args), str(kwargs) ))
                logger.write('  :Internet Archive Online\n')
                logger.flush()   
            if check_overload == True:
                overload_status = wait_if_overload(once = True)  
                if overload_status == 0:
                    return f(*args, **kwargs)                
                if logger:
                    logger.write("%s  func:%s  args:%s%s\n" %(str(datetime.now()), f.__name__, args, kwargs))
                    logger.write('  :Internet Archive Overload\n')
                    logger.flush()
                wait_if_overload()
                if logger:
                    logger.write("%s  func:%s  args:%s%s\n" %(str(datetime.now()), f.__name__, args, kwargs))
                    logger.write('  :Internet Archive Overload Restored \n')  
		    logger.flush()
            return f(*args, **kwargs)    
        return f_retry
      if f is None: # in this case, the decorator is called with arguments
            def decorator(f):
                return f_deco(f)
            return decorator
      # or the decorator is called without arguments
      return f_deco(f) 


"""Override requests.get method to include the retry wrapper defined above"""
requests.__dict__["new_get"] = requests.__dict__["get"]
@retry
def new_get(*args, **kwargs):
    return requests.__dict__["new_get"](*args, **kwargs)
requests.__dict__["get"] = new_get 


