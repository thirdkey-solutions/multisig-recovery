from pycoin.tx import Tx, pay_to, Spendable
import json
import multisigcore
import multisigcore.oracle
import sys
from . import PyBitcoinTools


def full_leaf_path(account_path, leaf_path):
	return '/%s/%s' % (account_path.strip('/'), leaf_path.strip('/'))


class Batch(object):

	@classmethod
	def from_file(cls, file_path):
		with open(file_path, 'r') as fp:
			data = json.load(fp)
		header = data['header']
		return cls(
			original_master_xpubs=header['original_master_xpubs'], destination_master_xpubs=header['destination_master_xpubs'],
			merkle_root=header['merkle_root'], total_out=header['total_out'], checksum=header['checksum'],
			batchable_txs=[BatchableTx.from_dict(tx) for tx in data['txs']],
		)

	def __init__(self, original_master_xpubs, destination_master_xpubs, batchable_txs, merkle_root=None, total_out=None, total_fee=None, checksum=None):
		self.original_master_xpubs = original_master_xpubs
		self.destination_master_xpubs = destination_master_xpubs
		self.batchable_txs = batchable_txs
		self.merkle_root = merkle_root or self._merkle_root()
		self.total_out = total_out or sum([batchable_tx.total_out() for batchable_tx in batchable_txs])
		self.checksum = checksum or -1  # todo - checksum

	def _merkle_root(self):  # todo - real merkle root
		return hash(','.join(sorted([batchable_tx.as_hex() for batchable_tx in self.batchable_txs])))

	def to_file(self, file_path):
		data = {
			'header': {
				'original_master_xpubs': self.original_master_xpubs, 'destination_master_xpubs': self.destination_master_xpubs,
				'merkle_root': self.merkle_root, 'total_out': self.total_out, 'checksum': self.checksum
			},
			'txs': [batchable_tx.as_dict() for batchable_tx in self.batchable_txs],
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
		for tx_i, batchable_tx in enumerate(self.batchable_txs):
			keys = ['%x' % master_private_key.subkey_for_path(path.strip('/')).secret_exponent() for path in batchable_tx.input_paths]
			d = batchable_tx.as_dict()
			try:
				d['bytes'] = PyBitcoinTools.cosign(d['bytes'], keys=keys)
				self.batchable_txs[tx_i] = BatchableTx.from_dict(d)
				print 'signed %s' % self.batchable_txs[tx_i].id()
			except ValueError:
				print '! could not sign tx %s, skipping' % self.batchable_txs[tx_i].id()
		self.merkle_root = self._merkle_root()

	def broadcast(self, provider):  # todo - broadcasting status will need to be cached to FS + checking blockchain until all txs pushed
		for batchable_tx in self.batchable_txs:
			try:
				provider.send_tx(batchable_tx)
				print 'broadcasted %s %s' % (batchable_tx.id(), batchable_tx.as_hex())
			except Exception, err:
				sys.stderr.write("! tx %s failed to propagate [%s] (%s)\n" %(batchable_tx.id(), batchable_tx.as_hex(), str(err)))

	def __repr__(self):
		return "Batch(%s)" % str(self.merkle_root)

	def __eq__(self, other):  # todo - think through more
		"""used for extensive validation - compare received copy with self-created copy"""
		return self.merkle_root == other.merkle_root and self.original_master_xpubs == other.master_xpubs and self.total_out == other.total_out and \
			self.total_fee == other.total_fee and self.checksum == other.checksum and len(self.batchable_txs) == len(other.batchable_txs)


class BatchableTx(Tx):

	@classmethod
	def from_dict(cls, data):
		batchable_tx = cls.tx_from_hex(data['bytes'])
		batchable_tx.output_paths = data['output_paths']
		batchable_tx.input_paths = data['input_paths']
		return batchable_tx

	@classmethod
	def from_tx(cls, tx, output_paths, backup_account_path, inject_hex=None):
		batchable_tx = cls(tx.version, tx.txs_in, tx.txs_out, tx.lock_time, tx.unspents)
		batchable_tx.input_paths = [full_leaf_path(backup_account_path, leaf_path) for leaf_path in tx.input_chain_paths()]
		batchable_tx.output_paths = [full_leaf_path(backup_account_path, leaf_path) for leaf_path in output_paths]
		if inject_hex is not None:
			d = batchable_tx.as_dict()
			d['bytes'] = inject_hex
			batchable_tx = cls.from_dict(d)
		return batchable_tx

	def as_dict(self):
		hex = self.as_hex()
		big = self.as_hex(include_unspents=True)
		return {  # todo - make it more similar to multisigcore.hierarchy.AccountTx
			'bytes': big,
			'input_paths': self.input_paths,
			'output_paths': self.output_paths,
		}

	def validate(self):
		if False:  # todo - validate tx
			raise ValueError('%s did not pass validation' % repr(self))