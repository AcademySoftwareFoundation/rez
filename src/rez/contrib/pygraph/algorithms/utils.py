# Copyright (c) 2008-2009 Pedro Matiello <pmatiello@gmail.com>
#                         Roy Smith <roy@panix.com>
#                         Salim Fadhley <sal@stodge.org>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.


"""
Miscellaneous useful stuff.
"""

# Imports
from heapq import heappush, heappop, heapify


# Priority Queue
class priority_queue:
    """
    Priority queue.
    """
    
    def __init__(self, list=[]):
        self.heap = [HeapItem(i, 0) for i in list]
        heapify(self.heap)

    def __contains__(self, item):
        for heap_item in self.heap:
            if item == heap_item.item:
                return True
        return False

    def __len__(self):
        return len(self.heap)

    def empty(self):
        return len(self.heap) == 0

    def insert(self, item, priority):
        """
        Insert item into the queue, with the given priority.
        """
        heappush(self.heap, HeapItem(item, priority))

    def pop(self):
        """
        Return the item with the lowest priority, and remove it from the queue.
        """
        return heappop(self.heap).item

    def peek(self):
        """
        Return the item with the lowest priority. The queue is unchanged.
        """
        return self.heap[0].item

    def discard(self, item):
        new_heap = []
        for heap_item in self.heap:
            if item != heap_item.item:
                new_heap.append(heap_item)
        self.heap = new_heap
        heapify(self.heap)

class HeapItem:
    def __init__(self, item, priority):
        self.item = item
        self.priority = priority

    def __cmp__(self, other):
        return cmp(self.priority, other.priority)
