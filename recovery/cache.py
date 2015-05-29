__author__ = 'Tom James Holub'

import os.path
import json


class Cache():

	ACCOUNT = 'account'
	TX = 'tx'

	def __init__(self, batch_id, path='./cache/'):
		self.path_template = os.path.join(path, batch_id, '%s/')
		self.fake_storage = {  # todo - use FS instead of memory
			self.__path(self.ACCOUNT): {},
			self.__path(self.TX): {},
		}

	def __path(self, type):
		return self.path_template % type

	def save(self, type, index, data):
		self.fake_storage[self.__path(type)][index] = json.dumps(data)

	def exists(self, type, index):
		return index in self.fake_storage[self.__path(type)]

	def load(self, type, index):
		return json.loads(self.fake_storage[self.__path(type)][index]) if self.exists(type, index) else None

	def count(self, type):
		return len(self.fake_storage[self.__path(type)])