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


import redis
import time
import mysql_py

import keys


def Redis():
    redis_host = keys.redis_host
    redis_port = keys.redis_port
    return redis.Redis(host=redis_host, port=redis_port)


db = mysql_py.Db()
redisg = Redis()    

class Lock(object):
    """A Lock based on Redis Key value system."""
    def __init__(self, key):     
        self.key = key
        self.redis = Redis()
        
    def acquire(self, timeout=0):
        while self.redis.get(self.key) is '1':
            time.sleep(0.1)
            continue
        self.redis.set(self.key, '1')
        if timeout != 0:
            self.redis.expire(self.key, time=timeout)
        return True
        
    def release(self):
        self.redis.delete(self.key)


def get(key, book_cache=False):
    redisg = Redis()
    info = redisg.get(key)
    if info in (-1, None) and book_cache:
        key_elements = key.split(':')
        if len(key_elements) > 2:
            library = key_elements[1]
            ia_identifier = key_elements[2]
            column_type = key_elements[3].lower()
            if column_type == 'sno':
                column_type = 'connected_request_sno'
        else:
            return None
        db_info = db.execute("select "+column_type+" from book where library = %s and book_id = %s;", library, ia_identifier)
        if db_info == None or db_info == []:
            return None
        elif db_info[0] == None or db_info[0][0] == None:
            return None
        else:
            redisg.set(key, db_info[0][0])
            return db_info[0][0]
    else:
        return info


def set(key, value, book_cache=False):
    redisg = Redis()
    redisg.set(key, value)
    if book_cache:
        key_elements = key.split(':')
        if len(key_elements) > 2:
            library = key_elements[1]
            ia_identifier = key_elements[2]
            column_type = key_elements[3].lower()
            if column_type == 'sno':
                column_type = 'connected_request_sno'
        else:
            return None
        db.execute("update book set "+column_type+" = %s where book_id = %s and library = %s", value, ia_identifier, library)


def sadd(key, value, request_cache=True):
    redis = Redis()
    redisg.sadd(key, value)
    if request_cache:
        key_elements = key.split(':')
        if len(key_elements) > 2:
            library = key_elements[1]
            ia_identifier = key_elements[2]
            column_type = key_elements[3]
        else:
            return None
        db.execute("insert into global_request(data, book_id, library) values(%s, %s, %s);", value, ia_identifier, library)


def smembers(key, request_cache=False):
    redisg = Redis()
    value = redisg.smembers(key)
    if value != None:
        return value
    elif request_cache:
        key_elements = key.split(':')
        if len(key_elements) > 2:
            library = key_elements[1]
            ia_identifier = key_elements[2]
            column_type = key_elements[3]
        else:
            return None
        value = db.execute("select data from global_request where book_id=%s and library=%s",ia_identifier, library)
        for x in value:
            redisg.sadd(key, x)
        if value == None:
            return None
        v = [x[0] for x in value ]
        return v
    else:
        return None


class Queue(object):
    """A Queue based on the Redis sorted set data type."""
    def __init__(self, key):        
        self.key = key
        self.table = keys.get_queue_table_name(self.key)
        global db
        self.db = db
        self.redis = Redis()

    def add(self, data):
        """Add an item to the queue."""
        self.db.execute("insert into "+self.table+"(data) values (%s);", data)


    def pop(self, num=1, index=0):
	num = int(num)
	index = int(index)
        """Return one item from the front of the queue. Return False if no items are available."""
        self.sync_db(1000)        
        redis_count = int(self.redis.zcard(self.key))
        if redis_count < int(num+index) or num == -1:
            if num == -1:
                num = 9999999
            result = self.db.execute("select data from %s limit %s,%s" %(self.table, index, num))
            result = [x[0] for x in result]
        else: 
            result = self.redis.zrangebyscore(self.key, 0, time.time(), start=index, num=num, withscores=False)
        if result == None:
            return False
        if len(result) != 0:
            return result
        else:
            return False

    def remove(self, data):
        "Remove an item from the Queue"
        self.sync_db(1000)
        self.db.execute("delete from "+self.table+" where data = %s;", data)
        return self.redis.zrem(self.key, data)
        
    def index(self, data):
        self.sync_db(1000)
        return self.redis.zrank(self.key, data)

    def size(self):
        count = int(self.db.execute("select count(*) from %s;" %self.table)[0][0])
        return count


    def sync_db(self, limit=1000):
        """sync required when redis memeory clears out.(system failure?)"""
        db_queue_count = self.db.execute("select count(*) from %s;" %self.table)[0][0]
        top_db = self.db.execute("select data from %s limit 1;" %self.table)
        if top_db != None and len(top_db) != 0:
            top_db = top_db[0][0]
        else:
            top_db = None
        top_redis = self.redis.zrangebyscore(self.key, 0, time.time(), start=0, num=1, withscores=False)
        if db_queue_count == 0 or top_db != top_redis:
            for entry in self.redis.zrangebyscore(self.key, 0, time.time(), start=0, num=-1, withscores=False):
                self.redis.zrem(self.key, entry)
        redis_count = int(self.redis.zcard(self.key))
        if redis_count < limit and db_queue_count != limit and db_queue_count != 0:
            left = limit - redis_count
            entries = self.db.execute("select data from %s limit %s,%s;" %(self.table, redis_count, left))
            entries = [x[0] for x in entries]
            for entry in entries:
                score = time.time()
                self.redis.zadd(self.key, entry, score)



