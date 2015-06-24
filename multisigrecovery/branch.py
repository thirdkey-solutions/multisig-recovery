from multisigcore.oracle import OracleUnknownKeychainException, Oracle, PersonalInformation
import uuid
import requests
from multisigcore.hierarchy import MultisigAccount, AccountKey, MasterKey
import json
from pycoin.encoding import EncodingError

class Branch(object):

	def __init__(self, account_key_sources, account_template, provider):
		self.account = lambda account_index: account_template(account_key_sources, account_index, provider)
		self.master_key_names = [self.__key_source_string(key_source) for key_source in account_key_sources]
		self.needs_oracle = bool(sum([isinstance(source, OracleAccountPubkeys) for source in account_key_sources]))

		backup_account_path_template_map = {  # todo - this might become obsolete
			self.bip32_account: '%d',
			self.bip32_hardened_account: '%d',  # backup (3rd party) key is not hardened even when local key is hardened
			self.bitoasis_v1_account: '%d',
		}
		self.backup_account_path_template = backup_account_path_template_map[account_template]

	@property
	def id(self):
		return '_'.join(key_source_id[-10:] for key_source_id in sorted(self.master_key_names))

	@staticmethod
	def bip32_account(account_key_sources, account_index, provider, __hardened=False):
		account_derivation = lambda source, i: source.bip32_account(i, hardened=source.is_private() and __hardened)
		account_keys = Branch._account_keys(account_key_sources, account_index, account_derivation)
		account = MultisigAccount(keys=account_keys)
		account._provider = provider
		return account

	@staticmethod
	def bip32_hardened_account(account_key_sources, account_index, provider):
		return self.bip32_account(account_key_sources, account_index, provider, __hardened=True)

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
		legacy_backup_account_key = to_legacy(account_key_sources[1].bip32_account(account_index, hardened=False), is_backup_key=True)
		cryptocorp_key = account_key_sources[2].get(account_index, [legacy_local_account_key, legacy_backup_account_key])
		account_keys = [legacy_local_account_key, legacy_backup_account_key, cryptocorp_key]
		account = MultisigAccount(account_keys, num_sigs=2, sort=False, complete=True)
		account._provider = provider
		account.set_lookahead(0)  # todo - add lookahead later
		return account

	def __key_source_string(self, key_source):
		try:
			return key_source.hwif(as_private=False)
		except AttributeError:  # will put 'Dict' or 'Oracle' into id based on xpub source class
			return key_source.__class__.__name__.replace(AccountPubkeys.__name__, '')

	@staticmethod
	def _account_keys(account_key_sources, account_index, derive_account):
		account_keys = []
		for source in account_key_sources:
			if isinstance(source, MasterKey):
				account_keys.append(derive_account(source, account_index))
			elif isinstance(source, DictAccountPubkeys):
				account_keys.append(source.get(account_index))
			elif isinstance(source, OracleAccountPubkeys):
				assert source == account_key_sources[-1]  # oracle has to be the last source
				account_keys.append(source.get(account_index, account_keys))
			else:
				raise TypeError('Unknown account key source, can work with MasterKey or AccountPubkeys')
		return account_keys


class AccountPubkeys():

	@staticmethod
	def parse_string_to_account_key_source(string, register_oracle_accounts_file=False):

		if '.json' in string:
			return DictAccountPubkeys.from_file(string)

		if 'digitaloracle' in string:
			return OracleAccountPubkeys(string, register_accounts_file=register_oracle_accounts_file)

		try:
			return MasterKey.from_seed_hex(string)
		except (TypeError, EncodingError), err:
			pass

		try:
			return MasterKey.from_key(string)
		except (TypeError, EncodingError), err:
			pass

		raise ValueError('Unknown type for account key source: %s' % string)

	def get(self, account_index):
		raise NotImplementedError('Abstract class')


class DictAccountPubkeys(AccountPubkeys):

	@classmethod
	def from_file(cls, path):
		""" :param path: path to json file containing "{account_number1: xpub1, ...}"""
		with open(path) as fp:
			return cls(json.load(fp))

	def __init__(self, pubkeys_by_account_indexes):
		self.pubkeys = pubkeys_by_account_indexes

	def get(self, account_index):
		return AccountKey.from_hwif(self.pubkeys[account_index])


class OracleAccountPubkeys(AccountPubkeys):

	def __init__(self, base_cryptocorp_url, register_accounts_file=None):
		self.base_url = base_cryptocorp_url.strip('/') + '/'
		self.register_accounts_file = register_accounts_file
		if register_accounts_file:
			with open(register_accounts_file) as fp:
				self.register = json.load(fp)
		else:
			self.register = None

	def get(self, account_index, account_keys):  # todo - handle timeouts, bad connection
		tmp_account = MultisigAccount(account_keys[:], complete=False)
		tmp_oracle = Oracle(tmp_account, base_url=self.base_url, manager=self.register['manager'] if self.register is not None else None)
		try:
			tmp_oracle.get()
		except OracleUnknownKeychainException:
			if self.register is None:
				raise
			else:
				try:
					personal_info_dict = self.register['personal_info'][str(account_index)]
				except KeyError:
					raise ValueError('Account index %d missing in %s, could not register with CC' % (account_index, self.register_accounts_file))
				tmp_oracle.create(self.register['parameters'], PersonalInformation(**personal_info_dict))
		assert len(tmp_account.keys) == len(account_keys) + 1  # asserting that we fetched a missing key from oracle
		return tmp_account.keys[-1]  # return the oracle key (last one)