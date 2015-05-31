__author__ = 'Tom James Holub'

from multisigcore.oracle import OracleUnknownKeychainException
import uuid
import requests
from multisigcore.hierarchy import MultisigAccount, AccountKey


class Branch(object):

	def __init__(self, account_key_sources, account_template, provider):
		self.account = lambda account_index: account_template(account_key_sources, account_index, provider)
		self.master_key_names = [self.__key_source_string(key_source) for key_source in account_key_sources]

		ACCOUNT_PATH_TEMPLATES = {
			self.bitoasis_v1_account: '0H/%d',
			self.bip32_account: '%dH',
			self.bip44_account: '%dH/0/0',  # todo - simplification, purpose and coin_type always 0
		}
		self.account_path_template = ACCOUNT_PATH_TEMPLATES[account_template]

	def __key_source_string(self, key_source):
		try:
			return key_source.hwif(as_private=False)
		except AttributeError:  # will put 'Dict' or 'Oracle' into id based on xpub source class
			return key_source.__class__.__name__.replace(AccountPubkeys.__name__, '')

	@property
	def id(self):
		return '_'.join(key_source_id[-10:] for key_source_id in sorted(self.master_key_names))

	@staticmethod
	def bitoasis_v1_account(account_key_sources, account_index, provider):
		def to_legacy(bip32key, is_backup_key=False):
			return AccountKey(
				netcode=bip32key._netcode, chain_code=bip32key.chain_code(), depth=bip32key.tree_depth(), parent_fingerprint=b'\0\0\0\0',
				child_index= 0 if is_backup_key else bip32key.child_index(),
				secret_exponent=bip32key.secret_exponent() if bip32key.is_private() else None,
				public_pair=bip32key.public_pair() if not bip32key.is_private() else None,
			)
		legacy_local_account_key = to_legacy(account_key_sources[0].electrum_account(account_index))
		legacy_backup_account_key = to_legacy(account_key_sources[1].electrum_account(account_index), is_backup_key=True)
		cryptocorp_key = account_key_sources[2].get(legacy_local_account_key)
		account_keys = [legacy_local_account_key, legacy_backup_account_key, cryptocorp_key]
		account = MultisigAccount(account_keys, num_sigs=2, sort=False, complete=True)
		account._provider = provider
		account.set_lookahead(0)  # todo - add lookahead later
		return account

	"""
	Following functions will not work from xPubs as multisig-core is currently using hardened accounts.
	Might add 'hardened' flags to multisigcore.hierarchy.MasterKey functions to make this work.
	"""

	@staticmethod
	def bip32_account(master_keys, account_index):
		return MultisigAccount(keys=[master_key.bip32_account(account_index) for master_key in master_keys])

	@staticmethod
	def bip44_account(master_keys, account_index):
		return MultisigAccount(keys=[master_key.bip44_account(account_index) for master_key in master_keys])

	@staticmethod
	def electrum_account(master_keys, account_index):
		return MultisigAccount(keys=[master_key.electrum_account(account_index) for master_key in master_keys])


class AccountPubkeys():

	def get(self, account_index):
		raise NotImplementedError('Abstract class')


class DictAccountPubkeys(AccountPubkeys):

	def __init__(self, pubkeys_by_account_indexes):
		self.pubkeys = pubkeys_by_account_indexes

	def get(self, account_index):
		return AccountKey.from_hwif(self.pubkeys[account_index])


class OracleAccountPubkeys(AccountPubkeys):

	def __init__(self, base_cryptocorp_url):
		self.base_url = base_cryptocorp_url.strip('/')

	def get(self, local_account_key):
		account_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, str("urn:digitaloracle.co:%s" % local_account_key.hwif(as_private=False))))
		account_url = self.base_url + '/keychains/' + account_uuid
		try:
			remote_xpub = requests.get(account_url).json()['keys']['default'][0]
			return AccountKey.from_hwif(remote_xpub)
		except KeyError:  # todo - handle timeouts, bad connection
			raise OracleUnknownKeychainException(account_url)