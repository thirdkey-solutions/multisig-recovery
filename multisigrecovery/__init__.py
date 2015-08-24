
from multisigcore import LazySecretExponentDBWithNetwork
from pycoin.tx.pay_to import build_p2sh_lookup
from pycoin.serialize import h2b
from pycoin.tx.script.tools import opcode_list


def cosign(tx, keys, redeem_scripts=None):
	"""
	Utility for locally signing a multisig transaction.
	:param tx: Transaction to sign.
	:param redeem_scripts: Required when adding first signature only.
	:param keys: one key per transaction input
	:return:
	"""
	if not keys:  # Nothing to do
	    return
	if redeem_scripts:  # scripts supplied as a param
		raw_scripts = [script.script() for script in redeem_scripts]
	else:  # parsing scripts from tx
		raw_scripts = [h2b(opcode_list(script)[-1]) for script in [tx_in.script for tx_in in tx.txs_in] if script]
	lookup = build_p2sh_lookup(raw_scripts) if raw_scripts else None
	db = LazySecretExponentDBWithNetwork(keys[0]._netcode, [key.wif() for key in keys], {})
	tx.sign(db, p2sh_lookup=lookup)
