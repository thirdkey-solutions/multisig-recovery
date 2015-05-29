__author__ = 'Tom James Holub'

from batch import Batch, BatchableTx
from cache import Cache


def get_dummy_tx():
	hex = '01000000013df3afdbffbcdcbe150f9163cbb1ff51a2bc1d48a4aa9357da0c1b29f915c20600000000fdfe0000493046022100f01f5875f48792f526e215d2782447bfa718f7511476bf3190d25727580a3d2a022100aa5a50d884e6cbd1f69b1877fec2799499025806d2c4c5b25af076d78af5107001473044022013a926b3fd9d3d0efc365a08d268177b3cfddba8e08e4b6363159964cffc10b4022067840f9f816afbcd6ffaf8f82198547ffeb3ee2ab12082c058605c2e7fe5ea6a014c69522102d806249bbe2020e158256146a15ca044fe426806d6875a34d2045a287755ffcf21022182b236bc2ea39fbfa3f84c66409ed7317f5c2acc3ae25c376f18a441fcaaec2102eb4327bf2e824b220fa2958c3c381f263ff8c9827a132110467003b4ef0ec8c953aeffffffff02b06a21000000000017a91416fb6d13eb356b8a73b0fe74fde4531a6e5e70db8710270000000000001976a9144e4f27b8b2324d6d0b20b5e325120551a564bed188ac00000000'
	print "! not using insight"
	print "! inserting dummy tx"
	tx_dict = {
			'bytes': hex,
		    'input_paths': ['not implemented'],
		    'output_paths': ['not implemented'],
		    'input_txs': ['010000000128ecab5157f205935e447b262e27fb7835cf14878d66f808409959d35e218d9300000000fdfd0000483045022055adf30bf42e0c5537ed4f3d450f7ed568d88d8b3771ad2dc27f08820180a03d0221008845013936841a23cbb8246c008dc4077e2d0a4e12a3013fdfc3e2ac12d427ad014730440220328a655e2cd164862ada4bd77327698bc29f7c6519efa6d9cdff75ff806441f40220503afb67e05380a0979f9d4883ce2613a55ef8a40c6dfd8447bfc78b9622bf72014c69522103ce4af01cb7fec726236af01ee58cbfafa0af4b907db8d2084b0744a181a227ef21030f780e32842233c7346b3a4abe2bf3b3566435f0650c717fb4002862ad272cee21024ff8b2b61414ce607c410962677d8093ec1d0e58c5e5cad881f6544ea73f26e253aeffffffff02d0b821000000000017a914dc74caae24696401d0c391115215f1bed50250318710270000000000001976a9144e4f27b8b2324d6d0b20b5e325120551a564bed188ac00000000']
	}
	return BatchableTx.from_dict(tx_dict)


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

	def __init__(self, branch, provider, account_gap=10, leaf_gap=20, first_account=0):
		self.id = branch.id
		self.master_key_names = branch.master_key_names
		self.known_accounts = {}
		self.profider = provider
		self.cache = Cache(self.id)
		self.recover_account = lambda account_index: branch.account(account_index)
		# self.account_gap = account_gap
		# self.leaf_gap = leaf_gap
		# self.first_account = first_account

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
			'0': {v: None for v in external_leafs} if type(external_leafs) == list else internal_leafs,
			'1': {v: None for v in external_leafs} if type(external_leafs) == list else internal_leafs,
		}

	def recover_accounts(self):
		"""will pick up where left off due to caching"""
		for account_index, leafs in self.known_accounts.items():
			if not self.cache.exists(Cache.ACCOUNT, account_index):
				account = self.recover_account(account_index)
				self.cache.save(Cache.ACCOUNT, account_index, account.cache)

	def create_txs(self):
		"""will pick up where left off due to caching"""
		for account_index, leafs in self.known_accounts.items():
			dummy_tx = get_dummy_tx()  # todo - create real txs
			self.cache.save(Cache.TX, account_index, dummy_tx.as_dict())

	def export_to_batch(self, path, return_batch=False):  # todo: too much dict -> batchable_tx -> dict
		batchable_tx_dicts = [self.cache.load(Cache.TX, account_index) for account_index in self.known_accounts]
		batch = Batch(master_xpubs=self.master_key_names, batchable_txs=[BatchableTx.from_dict(batchable_tx_dict) for batchable_tx_dict in batchable_tx_dicts])
		batch.validate()
		batch.to_file(path)
		if return_batch:
			return batch