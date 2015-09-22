from pycoin.tx import Tx, pay_to, Spendable
from pycoin.serialize import b2h, b2h_rev, h2b, h2b_rev
from pycoin.merkle import merkle
from pycoin.encoding import double_sha256
from pycoin.convention import tx_fee, satoshi_to_mbtc
from pycoin.networks import address_prefix_for_netcode
from pycoin.services import spendables_for_address, get_tx_db

import json
import multisigcore
import multisigcore.oracle
import sys
from . import cosign

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
		self.merkle_root = merkle_root
		self.total_out = total_out or sum([batchable_tx.total_out() for batchable_tx in batchable_txs])
		self.checksum = checksum or -1  # todo - checksum

	def build_merkle_root(self):
		# shouldn't get called without transactions
		if not len(self.batchable_txs):
			return None
		else:
			return b2h_rev(merkle(sorted([tx.hash() for tx in self.batchable_txs]), double_sha256))


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

	def validate(self, provider=None):
		if self.merkle_root != self.build_merkle_root():
			raise ValueError("calculated merkle_root %s does not match stated merkle_root %s from header" % (self.build_merkle_root(), self.merkle_root))

		self.total_out = 0
		if provider is not None:
			print "Doing full, online validation."
			self.total_in = 0
			self.total_fee = 0
		else:
			print "Doing limited, offline validation."

		print "Validating %d transactions" % len(self.batchable_txs)
		for tx_index, tx in enumerate(self.batchable_txs):
			print "\n\nValidating tx#%d - %s" % (tx_index+1, tx.id())
			print "- Total out", tx.total_out()
			self.total_out += tx.total_out()
			if provider:
				print "Fetching %d UTXO..." % len(tx.txs_in)
				for idx, tx_in in enumerate(tx.txs_in):
					unspent_tx = provider.get_tx(tx_in.previous_hash)
					tx.unspents.append(unspent_tx.txs_out[tx_in.previous_index])

				print "- Total in", tx.total_in()
				self.total_in += tx.total_in()

				print "- Fee", tx.fee()
				self.total_fee += tx.fee()

				print "- Transaction Size", len(tx.as_hex())
				print "- Recommended Fee for Size ", tx_fee.recommended_fee_for_tx(tx)
				if tx.fee() > 100000 and tx.fee() > 2 * tx_fee.recommended_fee_for_tx(tx):
					raise ValueError("Very high fee in transaction %s" % tx.id())
				print "- Fee Percent", (tx.fee() * 100.00 / tx.total_out())
				print "- Bad Signatures", tx.bad_signature_count(), "of", len(tx.txs_in)

	def sign(self, master_private_key):  # todo - test to see if this needs to be cached to FS when signing 100k txs
		for tx_i, batchable_tx in enumerate(self.batchable_txs):
			try:
				cosign(batchable_tx, keys=[master_private_key.subkey_for_path(path.strip('/')) for path in batchable_tx.input_paths])
				print 'signed: %s' % batchable_tx.id()
			except Exception as err:
				print '! could not sign tx %s, skipping' % batchable_tx.id(), err

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
	def from_tx(cls, tx, output_paths, backup_account_path):
		batchable_tx = cls(tx.version, tx.txs_in, tx.txs_out, tx.lock_time, tx.unspents)
		batchable_tx.input_paths = [full_leaf_path(backup_account_path, leaf_path) for leaf_path in tx.input_chain_paths()]
		batchable_tx.output_paths = [full_leaf_path(backup_account_path, leaf_path) for leaf_path in output_paths]
		return batchable_tx

	def as_dict(self):
		hex = self.as_hex()
		big = self.as_hex(include_unspents=True)
		return {  # todo - make it more similar to multisigcore.hierarchy.AccountTx
			'bytes': big,
			'input_paths': self.input_paths,
			'output_paths': self.output_paths,
		}
