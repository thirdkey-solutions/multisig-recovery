__author__ = 'Tom James Holub'

from pycoin.tx import Tx
import json


class Batch(object):

	@classmethod
	def from_file(cls, file_path):
		with open(file_path, 'r') as fp:
			data = json.load(fp)
		header = data['header']
		return cls(
			master_xpubs=header['master_xpubs'], batchable_txs=[BatchableTx.from_dict(tx) for tx in data['txs']],
			merkle_root=header['merkle_root'], total_out=header['total_out'], checksum=header['checksum']
		)

	def __init__(self, master_xpubs, batchable_txs, merkle_root=None, total_out=None, total_fee=None, checksum=None):
		self.master_xpubs = master_xpubs
		self.batchable_txs = batchable_txs
		self.merkle_root = merkle_root or hash(','.join(sorted([batchable_tx.as_hex() for batchable_tx in batchable_txs])))  # todo - real merkle root
		self.total_out = total_out or sum([batchable_tx.total_out() for batchable_tx in batchable_txs])
		self.checksum = checksum or -1  # todo - checksum

	def to_file(self, file_path):
		data = {
			'header': {'master_xpubs': self.master_xpubs, 'merkle_root': self.merkle_root, 'checksum': self.checksum, 'total_out': self.total_out},
		    'txs': [batchable_tx.as_dict() for batchable_tx in self.batchable_txs]
		}
		with open(file_path, 'w') as fp:
			print "save %s" % file_path
			json.dump(data, fp)

	def validate(self):
		if False:  # todo - validate header
			raise ValueError('%s did not pass validation', repr(self))
		for batchable_tx in self.batchable_txs:
			batchable_tx.validate()
		print '! validation not implemented'

	def sign(self, master_private_key):  # todo - test to see if this needs to be cached to FS when signing 100k txs
		for batchable_tx in self.batchable_txs:
			for output_path in batchable_tx.output_paths:
				print "! signing not implemented"  # todo - key derivation, signing

	def broadcast(self, provider):  # todo - broadcasting status will need to be cached to FS
		for batchable_tx in self.batchable_txs:
			# provider.push_tx(...) - todo - proadcasting, checking blockchain until all txs pushed
			pass

	def __repr__(self):
		return "Batch(%s)" % str(self.merkle_root)

	def __eq__(self, other):  # todo - think through more
		"""used for extensive validation - compare received copy with self-created copy"""
		return self.merkle_root == other.merkle_root and self.master_xpubs == other.master_xpubs and self.total_out == other.total_out and \
			self.total_fee == other.total_fee and self.checksum == other.checksum and len(self.batchable_txs) == len(other.batchable_txs)


class BatchableTx(Tx):

	@classmethod
	def from_dict(cls, data):
		batchable_tx = cls.tx_from_hex(data['bytes'])
		batchable_tx.add_signing_info(data['input_paths'], data['output_paths'], [Tx.tx_from_hex(input_tx) for input_tx in data['input_txs']])
		return batchable_tx

	def add_signing_info(self, input_paths, output_paths, input_txs):
		self.input_paths = input_paths
		self.output_paths = output_paths
		self.input_txs = input_txs

	def as_dict(self):
		return {  # todo - make it more similar to multisigcore.hierarchy.AccountTx
			'bytes': self.as_hex(),
		    'input_paths': self.input_paths,
		    'output_paths': self.output_paths,
		    'input_txs': [tx.as_hex() for tx in self.input_txs]
		}

	def validate(self):
		if False:  # todo - validate tx
			raise ValueError('%s did not pass validation' % repr(self))

