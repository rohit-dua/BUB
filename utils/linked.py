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


import redis_py, keys



def queue_key(index):
    redis_key4 = keys.redis_key4
    if index == 1:
        worker_queue_key = "%s:mass_worker" %(redis_key4)  
    else:
        worker_queue_key = "%s:mass_worker_%s" %(redis_key4, index)
    return worker_queue_key  


def get_id_from_another_worker(calling_worker_key, workers = 2):
    q_size_list = []
    q_list = []
    for i in range(1, workers+1):
        worker_queue_key = queue_key(i)
        #print worker_queue_key,
        if calling_worker_key == worker_queue_key:
            q_list.append(0)
            q_size_list.append(0)
            continue
        q = redis_py.Queue(worker_queue_key)
        q_list.append(q)
        q_size_list.append(q.size())
    max_size = max( q_size_list )
    if max_size == 0:
        return False
    largest_queue_index = q_size_list.index(max_size)
    largest_queue = q_list[ largest_queue_index ]
    Lock = redis_py.Lock( queue_key(largest_queue_index) + ":pop" )
    Lock.acquire()
    item = largest_queue.pop()
    if item!= False:
        largest_queue.remove(item[0])
        Lock.release()
        return item[0]
    else:
        Lock.release()
        return False    
  
