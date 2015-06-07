from multisigcore.hierarchy import MasterKey
from multisigcore.hierarchy import MultisigAccount
from multisigcore.providers.insight import Spendable, BatchService, InsightBatchService
from multisigcore.oracle import fix_input_script
import multisigcore

def print_tx(tx, text):
	print text, ('(bad sig count: %d, len: %d)' % (tx.bad_signature_count(), len(tx.as_hex()))), tx.id(), tx.as_hex()

master = MasterKey.from_seed_hex('54b426b3e676649e8bfd66a2943f56fe74da2d2c0934d78db3a87dae44ed8d159e29ea93f6f33550a767c228786e75d020753575733bcf336943f7fa4ecfd37f')
key_local = master.subkey_for_path('0H')
key_oracle = master.subkey_for_path('1H')
key_tks = master.subkey_for_path('4H')
keys = [key_local, key_oracle.public_copy(), key_tks.public_copy()]

account = MultisigAccount(keys=keys, num_sigs=2, complete=True)
account._provider = InsightBatchService('http://54.77.162.76:4001/')
account.set_lookahead(3)
print account.address(0)

# create tx
tx = account.tx([('1JvZh1nDzpZpRRuLELvL8Auh5zxGQFVoKT', 1000)], change_address=account.address(0))
print_tx(tx, 'new         ')
scripts = [account.script_for_path(tx_in.path) for tx_in in tx.txs_in]

# local signature
account.sign(tx)
print_tx(tx, 'local signed')

# backup signature
multisigcore.local_sign(tx, scripts, [key_tks.subkey_for_path(tx_in.path) for tx_in in tx.txs_in])
print_tx(tx, 'bakcup signed ')

for tx_in in tx.txs_in:
	fix_input_script(tx_in, account.script_for_path(tx_in.path).script())
print_tx(tx, 'fixed       ')

print 'tx.bad_signature_count()', tx.bad_signature_count()