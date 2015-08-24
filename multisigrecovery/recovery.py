from batch import Batch, BatchableTx, Tx
from cache import Cache
from multisigcore.hierarchy import TX_FEE_PER_THOUSAND_BYTES, InsufficientBalanceException, MasterKey, AccountTx
from multisigcore.oracle import OracleUnknownKeychainException
from pycoin.services.tx_db import TxDb


class CachedRecovery(object):
	"""
	Create a batch of transactions from master branch keys. Will cache each step and pick up where left off.
	"""

	def __init__(self, origin_branch, destination_branch, provider, account_gap=5, leaf_gap=5, first_account=0):  # todo - increase gaps
		self.origin_branch = origin_branch
		self.destination_branch = destination_branch
		self.cache = Cache(self.origin_branch.id)
		self.known_accounts = {}
		self.tx_db = TxDb(lookup_methods=[provider.get_tx], read_only_paths=[],	writable_cache_path='./cache/tx_db')
		self.account_gap = account_gap
		self.leaf_gap = leaf_gap
		self.first_account = first_account
		self.account_lookahead = True
		self.total_to_recover = 0

	def add_known_account(self, account_index, external_leafs=None, internal_leafs=None):
		"""
		Adding known account indexes speeds up recovery.
		If leafs are specified, these will be the only ones recovered(LEAF_GAP_LIMIT not used).
		If leafs are not specified, addresses will be recovered using LEAF_GAP_LIMIT.
			batch.add_known_account(0)
			batch.add_known_account(1, external_leafs=[0,1,2,3,4], internal_leafs=[0,1,2])
			batch.add_known_account(1, external_leafs={0: "receiving addr 0", 1: "receiving addr 1", ...}, internal_leafs={0: "change addr 0", ...})
		"""
		external_leafs = external_leafs or {}
		internal_leafs = internal_leafs or {}
		self.known_accounts[int(account_index)] = {  # each branch stored as {leaf_i: None or receiving address, ...} or None
			0: {int(v): None for v in external_leafs} if type(external_leafs) == list else {int(k): v for k, v in external_leafs.items()},
			1: {int(v): None for v in internal_leafs} if type(internal_leafs) == list else {int(k): v for k, v in external_leafs.items()},
		}
		self.account_lookahead = False

	def recover_origin_accounts(self):
		"""will pick up where left off due to caching"""
		if not self.account_lookahead:  # accounts already known
			for account_index, leafs in self.known_accounts.items():
				existed = self.recover_origin_account(account_index, internal_leafs=leafs[0], external_leafs=leafs[1])
				if not existed:
					self.known_accounts[account_index] = False
		else:  # searching for accounts
			accounts_ahead_to_check = self.account_gap
			while accounts_ahead_to_check:
				account_index = max(self.known_accounts.keys()) + 1 if self.known_accounts else 0
				existed = self.recover_origin_account(account_index)
				if existed:
					accounts_ahead_to_check = self.account_gap
					self.known_accounts[account_index] = True
				else:
					accounts_ahead_to_check -= 1
					self.known_accounts[account_index] = False

	def recover_origin_account(self, account_index, internal_leafs=None, external_leafs=None):
		"""
		:returns bool account_found
		If Oracle is one of account sources, will return True on success from Oracle.
		Else, will return True if there is any balance on the acct.
		"""
		# todo - balance caching so we don't pull it repeatedly for each acct
		# todo - not exising accounts should get cached too so we don't go through it again
		account = self.cache.load(Cache.ORIGINAL_ACCOUNT, account_index)
		if account is None:
			try:
				account = self.origin_branch.account(account_index)
				if internal_leafs is None or external_leafs is None:
					account.set_lookahead(self.leaf_gap)
					previous_balance = 0
					while True:
						address_map = account.make_address_map(do_lookahead=True)
						balance = account.balance()
						if balance == previous_balance:
							for address, path in address_map.items():
								print 'original %d/%s %s' % (account_index, path, address)
							break
						else:
							account._cache['issued']['0'] += self.leaf_gap  # todo - can be optimized
							account._cache['issued']['0'] += self.leaf_gap
							previous_balance = balance
				else:
					account.set_lookahead(0)
					for for_change, leaf_n_array in [(0, internal_leafs), (1, external_leafs)]:
						for leaf_n in leaf_n_array:
							address = account.address(leaf_n, change=int(for_change))  # this will get cached in the account object
							print "original %d/%d/%d %s" % (account_index, for_change, leaf_n, address)
				self.cache.save(Cache.ORIGINAL_ACCOUNT, account_index, account)
			except OracleUnknownKeychainException:
				print "! account %d: unkown" % account_index
				self.cache.save(Cache.ORIGINAL_ACCOUNT, account_index, False)
				return False  # todo - needs more sophisticated checks, eg bad connection, CC timeouts, etc
		return True if self.origin_branch.needs_oracle else bool(account.balance())

	def recover_destination_accounts(self):
		"""will pick up where left off due to caching"""
		for account_index in self.known_accounts:
			if self.known_accounts[account_index] and not self.cache.exists(Cache.DESTINATION_ACCOUNT, account_index):
				account = self.destination_branch.account(account_index)
				address = account.address(0, change=False)  # this will get cached in the account object
				print "destination %d/%d/%d %s" % (account_index, 0, 0, address)
				self.cache.save(Cache.DESTINATION_ACCOUNT, account_index, account)

	def create_and_sign_tx(self, account_index):
		if not self.known_accounts[account_index]:
			return False
		origin_account = self.cache.load(Cache.ORIGINAL_ACCOUNT, account_index)
		destination_account = self.cache.load(Cache.DESTINATION_ACCOUNT, account_index)
		destination_address = destination_account.address(0, False)  # from cache
		balance = origin_account.balance()
		balance_less_fee = balance - TX_FEE_PER_THOUSAND_BYTES
		account_tx = None
		while balance_less_fee > 0:
			try:  # todo - a function in multisigcore to withdraw all funds less fee
				account_tx = origin_account.tx([(destination_address, balance_less_fee)])
				self.total_to_recover += balance_less_fee
				print "account", account_index, "balance:", balance, ", fee:", balance - balance_less_fee, ", recovering:", balance_less_fee, "in", account_tx.id()
				break
			except InsufficientBalanceException, err:
				balance_less_fee -= TX_FEE_PER_THOUSAND_BYTES
		else:
			print "account", account_index, "balance:", balance, ",nothing to send"

		if account_tx is not None:
			account_path = self.origin_branch.backup_account_path_template % account_index
			origin_account.sign(account_tx)
			return BatchableTx.from_tx(account_tx, output_paths=['0/0'], backup_account_path=account_path)

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
			if batchable_tx:
				batchable_txs.append(batchable_tx)
		batch = Batch(self.origin_branch.master_key_names, self.destination_branch.master_key_names, batchable_txs=batchable_txs)
		batch.validate()
		batch.to_file(path)
		if return_batch:
			return batch