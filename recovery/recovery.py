__author__ = 'Tom James Holub'

from batch import Batch, BatchableTx
from cache import Cache
from multisigcore.hierarchy import TX_FEE_PER_THOUSAND_BYTES, InsufficientBalanceException, MasterKey, ElectrumMasterKey
from multisigcore.oracle import OracleUnknownKeychainException
from pycoin.services.tx_db import TxDb



class CachedRecovery(object):
	"""
	Create a batch of transactions from master branch keys. Will cache each step and pick up where left off.

	Needs to be universal, and work with any of:
	 - [ BO seed|m-xPub , TKS xPub , CC API ]
	 - [ BO seed|m-xPub , TKS xPub , CC xPubs export from BO db ]
	 - per-account xPub exports of all three (convenient for CC)
	or any other general use.

	Very early prototype.
	"""

	def __init__(self, original_branch, destination_branch, provider, account_gap=10, leaf_gap=20, first_account=0):
		self.original_branch = original_branch
		self.destination_branch = destination_branch
		self.cache = Cache(self.original_branch.id)
		self.known_accounts = {}
		self.tx_db = TxDb(lookup_methods=[provider.get_tx], read_only_paths=[],	writable_cache_path='./cache/tx_db')

		# self.account_gap = account_gap
		# self.leaf_gap = leaf_gap
		# self.first_account = first_account

#	def _full_leaf_path(self, account_path_template, account_index, for_change, n):
#		return '/%s/%d/%d' % (account_path, int(for_change), n)

	def add_known_account(self, account_index, external_leafs=None, internal_leafs=None):
		"""
		Adding known account indexes speeds up recovery.
		If leafs are specified, these will be the only ones recovered(LEAF_GAP_LIMIT not used).
		If leafs are not specified, addresses will be recovered using LEAF_GAP_LIMIT.
			batch.add_known_account(0)
			batch.add_known_account(1, external_leafs=[0,1,2,3,4], internal_leafs=[0,1,2])
			batch.add_known_account(1, external_leafs={0: "receiving addr 0", 1: "receiving addr 1", ...}, internal_leafs={0: "change addr 0", ...})
		"""
		self.known_accounts[account_index] = {  # each branch stored as {leaf_i: None or receiving address, ...} or None
			'0': {v: None for v in external_leafs} if type(external_leafs) == list else external_leafs,
			'1': {v: None for v in internal_leafs} if type(internal_leafs) == list else internal_leafs,
		}

	def recover_original_accounts(self):
		"""will pick up where left off due to caching"""
		for account_index, leafs in self.known_accounts.items():
			if not self.cache.exists(Cache.ORIGINAL_ACCOUNT, account_index):
				try:
					account = self.original_branch.account(account_index)
					for for_change, leaf_n_array in leafs.items():
						for leaf_n in leaf_n_array:
							address = account.address(leaf_n, change=int(for_change))  # this will get cached in the account object
							print "recovered", account_index, for_change, leaf_n, address
					self.cache.save(Cache.ORIGINAL_ACCOUNT, account_index, account)
				except OracleUnknownKeychainException:
					print "unknown acct", account_index
					del self.known_accounts[account_index]  # todo - needs more sophisticated checks, eg bad connection, CC timeouts, etc

	def recover_destination_accounts(self):
		"""will pick up where left off due to caching"""
		for account_index in self.known_accounts:
			if not self.cache.exists(Cache.DESTINATION_ACCOUNT, account_index):
				account = self.destination_branch.account(account_index)
				address = account.address(0, change=False)  # this will get cached in the account object
				print "destination", account_index, 0, 0, address
				self.cache.save(Cache.DESTINATION_ACCOUNT, account_index, account)

	def create_and_sign_tx(self, account_index):
		original_account = self.cache.load(Cache.ORIGINAL_ACCOUNT, account_index)
		destination_account = self.cache.load(Cache.DESTINATION_ACCOUNT, account_index)
		destination_address = destination_account.address(0, False)  # from cache
		balance = original_account.balance()
		balance_less_fee = balance - TX_FEE_PER_THOUSAND_BYTES
		tx = None
		while balance_less_fee > 0:
			try:  # todo - a function in multisigcore to withdraw all funds less fee
				tx = original_account.tx([(destination_address, balance_less_fee)])
				print "account", account_index, "balance:", balance, ", fee:", balance - balance_less_fee, ", recovering:", balance_less_fee, "in", tx.id()
				break
			except InsufficientBalanceException, err:
				balance_less_fee -= TX_FEE_PER_THOUSAND_BYTES
		else:
			print "account", account_index, "balance is", balance, "- nothing to send"

		if tx is not None:
			account_path = self.original_branch.backup_account_path_template % account_index
			scripts = [original_account.script_for_path(tx_in.path) for tx_in in tx.txs_in]
			batchable_tx = BatchableTx.from_tx(tx, output_paths=['0/0'], scripts=scripts, backup_account_path=account_path, tx_db=self.tx_db)
			original_account.sign(batchable_tx)
			print '[first sign, saving] %d %s %s' % (batchable_tx.bad_signature_count(), batchable_tx.id(), batchable_tx.as_hex())
			return batchable_tx

	def create_and_sign_txs(self):
		"""will pick up where left off due to caching"""
		for account_index, leafs in self.known_accounts.items():
			if not self.cache.exists(Cache.TX, account_index):
				batchable_tx = self.create_and_sign_tx(account_index)
				self.cache.save(Cache.TX, account_index, batchable_tx)

	def export_to_batch(self, path, return_batch=False):
		batchable_txs = []
		for account_index in self.known_accounts:
			batchable_tx = self.cache.load(Cache.TX, account_index)
			if batchable_tx is not None:
				batchable_txs.append(batchable_tx)
		batch = Batch(self.original_branch.master_key_names, self.destination_branch.master_key_names, batchable_txs=batchable_txs)
		batch.validate()
		batch.to_file(path)
		if return_batch:
			return batch