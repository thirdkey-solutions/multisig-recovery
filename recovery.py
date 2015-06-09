#!/usr/bin/python

import argparse
import textwrap
import sys
from multisigcore.providers.insight import InsightBatchService
from multisigcore.hierarchy import MasterKey
from recovery.branch import Branch, AccountPubkeys
from recovery.recovery import CachedRecovery
from recovery.batch import Batch
import json

EXAMPLES = """
./recovery.py create --origin <KS1,KS2,KS3> --destination <KS1,KS2,KS3> --save <FILE>
./recovery.py cosign --load <FILE> --seed <SEED> --save <FILE>
./recovery.py broadcast --load <FILE>

KS(n) above is account key source: master key, a seed, or account keys service. Accepted formats:
 - extended public key (xpub69mdgvyDG2w...)
 - extended private key (xprv...)
 - seed in hex format (54b426b3e6766...)
 - CryptoCorp Oracle API URL (https://s.digitaloracle.co/)
 - Path to .json file with account_i:pubkey map (samples/account-keys.json)

Sample files:
 - samples/account-keys.json : If you cannot derive account keys of one of your partners (eg they use hardened accounts),
        you can supply a list of account indexes and xPubs as a json file. Typically, you would import this from your DB.
        Add this file as one of account key sources, eg: --origin seed1,samples/account-keys.json,xpub3
 - samples/known-accounts.json : Speed up recovery if you can export a list of created accounts from your DB. If not used,
        script will attempt to recover all accounts based on account and address gap limit. See the file for example
        formatting. Usage: --accounts samples/known-accounts.json
 """


class ScriptInputError(Exception):
	pass


def get_insight(url):
	insight = InsightBatchService(url)
	try:
		insight.get_blockchain_tip()
	except Exception:
		raise ScriptInputError('Insight node at %s not reachable' % url)
	return insight


def parse_key_sources(key_sources_string):
	try:
		return [AccountPubkeys.parse_string_to_account_key_source(string) for string in key_sources_string.split(',')]
	except ValueError, err:
		raise ScriptInputError(err.message)


def get_template(string):
	return getattr(Branch, '%s_account' % string)


def create(args):
	insight = get_insight(args.insight)

	# setup
	origin_branch = Branch(parse_key_sources(args.origin), get_template(args.template), provider=insight)
	destination_branch = Branch(parse_key_sources(args.destination), get_template(args.template), provider=insight)
	cached_recovery = CachedRecovery(origin_branch, destination_branch, provider=insight)

	# adding known accounts
	with open(args.accounts) as fp:
		known_accounts = json.load(fp)
	for account_number, indexes in known_accounts.items():
		if indexes is not None and 'external_leafs' in indexes and 'internal_leafs' in indexes:
			cached_recovery.add_known_account(account_number, external_leafs=indexes['external_leafs'], internal_leafs=indexes['internal_leafs'])
		else:
			cached_recovery.add_known_account(account_number)

	# recovery
	cached_recovery.recover_origin_accounts()
	cached_recovery.recover_destination_accounts()
	cached_recovery.create_and_sign_txs()
	cached_recovery.export_to_batch(args.save)


def cosign(args):
	backup_mpk = MasterKey.from_seed_hex(args.seed)
	batch = Batch.from_file(args.load)
	batch.validate()  # todo - validation
	batch.sign(master_private_key=backup_mpk)
	batch.to_file(args.save)


def broadcast(args):
	insight = get_insight(args.insight)
	batch = Batch.from_file(args.load)
	batch.validate()  # todo - validation
	batch.broadcast(provider=insight)


def main():
	parser = argparse.ArgumentParser(description='BitOasis multisig branch recovery script', formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument('command', choices=['create', 'cosign', 'broadcast'])
	parser.add_argument('--load', metavar='FILE', help='Load from batch file (cosign, broadcast)')
	parser.add_argument('--save', metavar='FILE', help='Save to batch file (create, cosign)')
	parser.add_argument('--origin', metavar='MKs', help='Original branch keys, comma separated (create)')
	parser.add_argument('--destination', metavar='MKs', help='Destination branch keys, comma separated (create)')
	parser.add_argument('--accounts', metavar='FILE', help='Use list of known account indexes. (create)')
	parser.add_argument('--insight', metavar='URL', help='Default: http://127.0.0.1:4001/ (create, broadcast)', default='http://127.0.0.1:4001/')
	parser.add_argument('--template', metavar='TYPE', help='Default: bip32', default='bip32', choices=['bitoasis_v1', 'bip32', 'bip32_hardened'])
	parser.add_argument('--seed', help='Signing hex seed (cosign)')
	parser.epilog = EXAMPLES
	args = parser.parse_args()

	arguments = {
		'create': {'load': False, 'origin': True, 'destination': True, 'seed': False, 'save': True},
	    'cosign': {'load': True, 'origin': False, 'destination': False, 'seed': True, 'save': True, 'accounts': False},
	    'broadcast': {'load': True, 'origin': False, 'destination': False, 'seed': False, 'save': False, 'accounts': False},
	}

	try:

		for argument, expected in arguments[args.command].items():
			supplied = getattr(args, argument) is not None
			if supplied and not expected:
				raise ScriptInputError('%s: unexpected argument: --%s\n' % (args.command, argument))
			if expected and not supplied:
				raise ScriptInputError('%s: missing argument: --%s\n' % (args.command, argument))

		if args.command == 'create':
			if args.accounts is None:
				raise NotImplementedError('Account and address lookahead/gaps not implemented. Please use "--accounts samples/known-accounts.json"')
			if args.origin != args.destination and 'https' in args.destination:
				raise NotImplementedError('Cannot create new CC Oracle accounts yet. Have destination equal to origin (for testing) or use non-oracle key sources for destination.')
			create(args)

		elif args.command == 'cosign':
			cosign(args)
		elif args.command == 'broadcast':
			broadcast(args)

	except (ScriptInputError, NotImplementedError), err:
		sys.stderr.write('%s: %s\n' % (err.__class__.__name__, err.message))


if __name__ == '__main__':
	main()