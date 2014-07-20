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

import keys


def Redis():
    redis_host = keys.redis_host
    redis_port = keys.redis_port
    return redis.Redis(host=redis_host, port=redis_port)
    
    
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


class Queue(object):
    """A Queue based on the Redis sorted set data type."""
    def __init__(self, key):        
        self.key = key
        self.redis = Redis()

    def add(self, data):
        """Add an item to the queue."""
        score = time.time()
        a=self.redis.zadd(self.key, data, score)

    def pop(self, num=1, index=0):
        """Return one item from the front of the queue. Return False if no items are available."""
        result = self.redis.zrangebyscore(self.key, 0, time.time(), start=index, num=num, withscores=False)
        if result == None:
            return False
        if len(result) != 0:
            return result
        else:
            return False

    def remove(self, data):
        "Remove an item from the Queue"
        return self.redis.zrem(self.key, data)
        
    def index(self, data):
        "Returns size of queue"
        return self.redis.zrank(self.key, data)

