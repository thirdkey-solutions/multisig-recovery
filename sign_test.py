from multisigcore.hierarchy import MasterKey
from multisigcore.hierarchy import MultisigAccount
from multisigcore.providers.insight import Spendable, BatchService

class FakeInsightBatchService(BatchService):
	def spendables_for_addresses(self, addresses):
		return [Spendable.from_dict({'script_hex': u'a914bb2998e6a7f1894482079f9de554ffbfe3579c5d87', 'does_seem_spent': 0, 'block_index_spent': 0,	'tx_hash_hex': u'b8270c9252a25d1b4585b78cdf994b45dc7cc0ad84234405ec8bb8a654be0a4f',	'coin_value': 10000, 'block_index_available': 0, 'tx_out_index': 0})]

def print_tx(tx, text):
	print text, ('(bad sig count: %d, len: %d)' % (tx.bad_signature_count(), len(tx.as_hex()))), tx.id(), tx.as_hex()

master_key_local = MasterKey.from_seed_hex('54b426b3e676649e8bfd66a2943f56fe74da2d2c0934d78db3a87dae44ed8d159e29ea93f6f33550a767c228786e75d020753575733bcf336943f7fa4ecfd37f')
master_key_backup = MasterKey.from_seed_hex('5e3db9f73124fde2f91484872776f878f5256a87ba72c1f515e7f11d46922d838a2f0c9245d32224f302cd9fb6760fb779bc1efbe681a2ad74be819d5a648b70')

account_key_local = master_key_local.subkey_for_path('0')
account_key_backup = master_key_backup.subkey_for_path('0')

account = MultisigAccount(keys=[account_key_local, account_key_backup.public_copy()], num_sigs=2, complete=True)
account_with_backup_seed = MultisigAccount(keys=[account_key_local.public_copy(), account_key_backup], num_sigs=2, complete=True)
account._provider = FakeInsightBatchService()

assert account.address(0) == account_with_backup_seed.address(0)

# create tx
tx = account.tx([(account.address(1), 1000)], change_address=account.address(0))
print_tx(tx, 'new    ')

# local signature
account.sign(tx)
print_tx(tx, 'one sig')

# backup signature
account_with_backup_seed.sign(tx)
print_tx(tx, 'signed ')

assert tx.bad_signature_count() == 0
