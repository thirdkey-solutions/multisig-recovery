__author__ = 'Tom James Holub'

from pycoin.tx import Tx, pay_to, Spendable
import json
import multisigcore
import multisigcore.oracle
import sys

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
		self.merkle_root = merkle_root or hash(','.join(sorted([batchable_tx.as_hex() for batchable_tx in batchable_txs])))  # todo - real merkle root
		self.total_out = total_out or sum([batchable_tx.total_out() for batchable_tx in batchable_txs])
		self.checksum = checksum or -1  # todo - checksum

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
		for batchable_tx in self.batchable_txs:
			keys = [master_private_key.subkey_for_path(path.strip('/')) for path in batchable_tx.input_paths]
			print '[first sign, loaded] %d %s %s' % (batchable_tx.bad_signature_count(), batchable_tx.id(), batchable_tx.as_hex())
			multisigcore.local_sign(batchable_tx, batchable_tx.scripts, keys)
			print '[second sign] %d %s %s' % (batchable_tx.bad_signature_count(), batchable_tx.id(), batchable_tx.as_hex())

	def broadcast(self, provider):  # todo - broadcasting status will need to be cached to FS + checking blockchain until all txs pushed
		for batchable_tx in self.batchable_txs:
			try:
				for i, tx_in in enumerate(batchable_tx.txs_in):
					multisigcore.oracle.fix_input_script(tx_in, batchable_tx.scripts[i].script())
				print '[after fix] %d %s %s' % (batchable_tx.bad_signature_count(), batchable_tx.id(), batchable_tx.as_hex())
				provider.send_tx(batchable_tx)
			except Exception, err:
				sys.stderr.write("tx %s failed to propagate (%s)\n" %(batchable_tx.id(), str(err)))

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
		batchable_tx.input_txs = [Tx.tx_from_hex(input_tx) for input_tx in data['input_txs']]
		batchable_tx.scripts = [pay_to.script_obj_from_script(script.decode('hex')) for script in data['scripts']]
		return batchable_tx

	@classmethod
	def from_tx(cls, tx, output_paths, scripts, backup_account_path, tx_db):
		batchable_tx = cls(tx.version, tx.txs_in, tx.txs_out, tx.lock_time, tx.unspents)
		batchable_tx.input_paths = [full_leaf_path(backup_account_path, leaf_path) for leaf_path in tx.input_chain_paths()]
		batchable_tx.output_paths = [full_leaf_path(backup_account_path, leaf_path) for leaf_path in output_paths]
		batchable_tx.scripts = scripts
		batchable_tx.input_txs = []
		for input in tx.txs_in:
			input_tx = tx_db.get(input.previous_hash)
			if input_tx is None:
				raise IOError("could not look up tx for %s" % (b2h(inp.previous_hash)))
			batchable_tx.input_txs.append(input_tx)
		return batchable_tx

	def as_dict(self):
		hex = self.as_hex()
		big = self.as_hex(include_unspents=True)
		return {  # todo - make it more similar to multisigcore.hierarchy.AccountTx
			'bytes': big,
			'input_paths': self.input_paths,
			'output_paths': self.output_paths,
			'input_txs': [tx.as_hex() for tx in self.input_txs],
		    'scripts': [script.script().encode('hex') for script in self.scripts],
		}

	def validate(self):
		if False:  # todo - validate tx
			raise ValueError('%s did not pass validation' % repr(self))