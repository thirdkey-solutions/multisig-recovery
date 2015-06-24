
import bitcoin
from pycoin.key.Key import Key


class PyBitcoinTools():

	@staticmethod
	def _order_script_signatures(tx, i, serialized_script):
		if not serialized_script:
			raise ValueError('Input %d is missing a redeem script' % i)
		script = bitcoin.deserialize_script(serialized_script)
		original_script = bitcoin.deserialize_script(script[-1])
		if len(script) - 2 != original_script[0]:  # Signing not complete. fixme - this is a blind guess.
			return serialized_script
		ordered_signatures = []
		for pubkey in original_script[1:-2]:
			uncompressed_pubkey = Key.from_sec(pubkey.decode('hex')).sec_as_hex(use_uncompressed=True)
			for signature in script[1:-1]:
				if bitcoin.verify_tx_input(tx, i, script[-1], signature, uncompressed_pubkey):
					ordered_signatures.append(signature)
					break
		if len(ordered_signatures) != original_script[0]:
			raise ValueError('Tx signing failed')
		return bitcoin.serialize_script([script[0]] + ordered_signatures + [script[-1]])

	@classmethod
	def _order_tx_signatures(cls, tx):
		deserialized_tx = bitcoin.deserialize(tx)
		for i, input in enumerate(deserialized_tx['ins']):
			input['script'] = cls._order_script_signatures(tx, i, input['script'])
		return bitcoin.serialize(deserialized_tx)

	@classmethod
	def cosign(cls, tx, keys, redeem_scripts=None):
		tx = bytes(tx)
		deserialized_tx = bitcoin.deserialize(tx)
		assert len(keys) == len(deserialized_tx['ins']) and (redeem_scripts is None or len(redeem_scripts) == len(keys))
		for i, key in enumerate(keys):
			script = deserialized_tx['ins'][i]['script']
			signatures = bitcoin.deserialize_script(script)[1:-1] if script else []
			redeem_script = redeem_scripts[i] if redeem_scripts is not None else bitcoin.deserialize_script(script)[-1]
			signatures.insert(0, bitcoin.multisign(tx, i, redeem_script, key))
			signed_tx = bitcoin.apply_multisignatures(tx, i, redeem_script, signatures)
			serialized_script = bitcoin.deserialize(signed_tx)['ins'][i]['script']
			deserialized_tx['ins'][i]['script'] = cls._order_script_signatures(tx, i, serialized_script)
		return bitcoin.serialize(deserialized_tx)