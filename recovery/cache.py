__author__ = 'Tom James Holub'

import os.path
#import json
import pickle

class Cache():

	ORIGINAL_ACCOUNT = 'original_account'
	DESTINATION_ACCOUNT = 'destination_account'
	TX = 'account_tx'

	def __init__(self, batch_id, path='./cache/'):
		self.path_template = os.path.join(path, batch_id, '%s/')
		self.fake_storage = {  # todo - use FS instead of memory
			self.__path(self.ORIGINAL_ACCOUNT): {},
			self.__path(self.DESTINATION_ACCOUNT): {},
			self.__path(self.TX): {},
		}

	def __path(self, type):
		return self.path_template % type

	def save(self, type, index, data):
		self.fake_storage[self.__path(type)][index] = pickle.dumps(data, protocol=-1)

	def exists(self, type, index):
		return index in self.fake_storage[self.__path(type)]

	def load(self, type, index):
		return pickle.loads(self.fake_storage[self.__path(type)][index]) if self.exists(type, index) else None

	def count(self, type):
		return len(self.fake_storage[self.__path(type)])