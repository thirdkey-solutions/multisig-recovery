
from multisigcore.hierarchy import MasterKey
import random

SEED_FILE = '_test-insecure.seed'


try:
	with open(SEED_FILE, 'r') as fp:
		insecure_seed_base = fp.read().strip()
except IOError:
	insecure_seed_base = ''.join([random.choice('0123456789abcdef') for i in range(0, 128)])  # please do not use this in production or you'll lose your coins
	with open(SEED_FILE, 'w') as fp:
		fp.write(insecure_seed_base)

def __rotate(string, times=1):
	for i in range(0, times):
		letters = list(string)
		letters.append(letters.pop(0))
		string = ''.join(letters)
	return string


# creating seeds
hex_seeds = [insecure_seed_base, __rotate(insecure_seed_base, 1), __rotate(insecure_seed_base, 2), __rotate(insecure_seed_base, 3)]
xpub_strings = [str(MasterKey.from_seed_hex(seed_hex).hwif()) for seed_hex in hex_seeds]


def get_test_master_keys():
	return [MasterKey.from_seed_hex(seed_hex) for seed_hex in hex_seeds]


def get_test_hex_seeds():
	return hex_seeds


def get_test_master_xpub_keys():
	return [MasterKey.from_hwif(hwif) for hwif in xpub_strings]


def get_test_master_xpub_strings():
	return xpub_strings


def to_bip32_accounts(keys, i, hardened=False):
	return [key.bip32_account(i, hardened=hardened) for key in keys]