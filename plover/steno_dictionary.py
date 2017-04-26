# Copyright (c) 2013 Hesky Fisher.
# See LICENSE.txt for details.

"""StenoDictionary class and related functions.

A steno dictionary maps sequences of steno strokes to translations.

"""

import collections
import csv

class StenoDictionary(collections.MutableMapping):
    """A steno dictionary.

    This dictionary maps immutable sequences to translations and tracks the
    length of the longest key.

    Attributes:
    longest_key -- A read only property holding the length of the longest key.
    save -- If set, is a function that will save this dictionary.

    """
    def __init__(self, *args, **kw):
        self._dict = {}
        self._longest_key_length = 0
        self._longest_listener_callbacks = set()
        self.reverse = collections.defaultdict(list)
        self.casereverse = collections.defaultdict(set)
        self.filters = []
        self.update(*args, **kw)
        self.save = None
        self._path = ''

    @property
    def longest_key(self):
        """The length of the longest key in the dict."""
        return self._longest_key

    def __len__(self):
        return self._dict.__len__()
        
    def __iter__(self):
        return self._dict.__iter__()

    def __getitem__(self, key):
        return self._dict.__getitem__(key)

    def __setitem__(self, key, value):
        self._longest_key = max(self._longest_key, len(key))
        self._dict[key] = value
        self.reverse[value].append(key)
        # Case-insensitive reverse dict
        self.casereverse[value.lower()].add(value)

    def __delitem__(self, key):
        value = self._dict.pop(key)
        self.reverse[value].remove(key)
        if len(key) == self.longest_key:
            if self._dict:
                self._longest_key = max(len(x) for x in self._dict)
            else:
                self._longest_key = 0

    def __contains__(self, key):
        return self.get(key) is not None

    def set_path(self, path):
        self._path = path    

    def get_path(self):
        return self._path    

    @property
    def _longest_key(self):
        return self._longest_key_length

    @_longest_key.setter
    def _longest_key(self, longest_key):
        if longest_key == self._longest_key_length:
            return
        self._longest_key_length = longest_key
        for callback in self._longest_listener_callbacks:
            callback(longest_key)

    def add_longest_key_listener(self, callback):
        self._longest_listener_callbacks.add(callback)

    def remove_longest_key_listener(self, callback):
        self._longest_listener_callbacks.remove(callback)


class StenoDictionaryCollection(object):

    def __init__(self, max_pos):
        self.dicts = []
        self.filters = []
        self.longest_key = 0
        self.longest_key_callbacks = set()
        self.max_possibilities = max_pos

    def set_dicts(self, dicts):
        for d in self.dicts:
            d.remove_longest_key_listener(self._longest_key_listener)
        self.dicts = dicts[:]
        self.dicts.reverse()
        for d in dicts:
            d.add_longest_key_listener(self._longest_key_listener)
        self._longest_key_listener()

    def _lookup(self, key, dicts=None, filters=()):
        if dicts is None:
            dicts = self.dicts
        key_len = len(key)
        if key_len > self.longest_key:
            return None
        for d in dicts:    
            if key_len > d.longest_key:
                continue
            value = d.get(key)
            if value:
                for f in filters:
                    if f(key, value):
                        return None
                return value

    def create_common_words_dict(self, fname):
        self.common_words_dict = ()
        try:
            reader = csv.DictReader(open(fname))
            for row in reader:
                self.common_words_dict += (row,)
        except Exception:
            return

    def findPossibleContinues(self, do, filters=()):
        key = do[0].rtfcre
        key_len = len(key)
        possibilities = {}
        currentKey = "current"
        curr_key = u""
        for i in range(0, len(key)):
            if(not i == 0 and not i == len(key)):
                curr_key += "/"    
            curr_key += key[i]
        tr = u"none"
        if(do[0].english):
            tr = do[0].english
        possibilities[(currentKey,)] = curr_key + u":" + tr + u":"
        for d in self.dicts:    
            if key_len > d.longest_key:
                continue
            for entry in d:
                if(self.isPossibleContinue(key, entry)):
                    entry_key = ()
                    for i in range(0,len(entry)):
                        entry_key += (str(entry[i]),)
                    possibilities[(entry,)] = d.get(entry_key) 
        return self.shrinkPossibilities(possibilities)

    def isPossibleContinue(self, key, entry):
        if(len(key) >= len(entry)):
            return False
        for i in range(0, len(key)):
            if(key[i] != entry[i]):
                return False
        return True

    def shrinkPossibilities(self, pos):
        if(len(pos) <= self.max_possibilities):
            return pos
        if(len(self.common_words_dict) == 0):
            return self.getFirstFewElements(pos)
        return self.getPopularElements(pos)

    def getFirstFewElements(self, pos):
        return {k: pos[k] for k in pos.keys()[:self.max_possibilities]}

    def getPopularElements(self, pos):
        # TODO: select the best max_possibilities 
        #       number of elements from pos 
        #       accoring to common_words_dict 
        return {k: pos[k] for k in pos.keys()[:self.max_possibilities]}



    def take(self, n, iterable):
        return list(islice(iterable, n))

    def set_max_possibilities(self, max_poss):
        self.max_possibilities = max_poss

    def lookup(self, key):
        return self._lookup(key, filters=self.filters)

    def raw_lookup(self, key):
        return self._lookup(key)

    def reverse_lookup(self, value):
        keys = []
        for n, d in enumerate(self.dicts):
            for k in d.reverse.get(value, ()):
                # Ignore key if it's overriden by a higher priority dictionary.
                if self._lookup(k, dicts=self.dicts[:n]) is None:
                    keys.append(k)
        return keys

    def casereverse_lookup(self, value):
        for d in self.dicts:
            key = d.casereverse.get(value)
            if key:
                return key

    def set(self, key, value, dictionary=None):
        if dictionary is None:
            d = self.dicts[0]
        else:
            d = self.get_by_path(dictionary)
        d[key] = value

    def save(self, path_list=None):
        '''Save the dictionaries in <path_list>.

        If <path_list> is None, all writable dictionaries are saved'''
        if path_list is None:
            dict_list = [dictionary
                         for dictionary in self.dicts
                         if dictionary.save is not None]
        else:
            dict_list = [self.get_by_path(path)
                         for path in path_list]
        for dictionary in dict_list:
            dictionary.save()

    def get_by_path(self, path):
        for d in self.dicts:
            if d.get_path() == path:
                return d

    def add_filter(self, f):
        self.filters.append(f)

    def remove_filter(self, f):
        self.filters.remove(f)

    def add_longest_key_listener(self, callback):
        self.longest_key_callbacks.add(callback)

    def remove_longest_key_listener(self, callback):
        self.longest_key_callbacks.remove(callback)
    
    def _longest_key_listener(self, ignored=None):
        if self.dicts:
            new_longest_key = max(d.longest_key for d in self.dicts)
        else:
            new_longest_key = 0
        if new_longest_key != self.longest_key:
            self.longest_key = new_longest_key
            for c in self.longest_key_callbacks:
                c(new_longest_key)
