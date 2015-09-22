from multisigcore.providers.insight import InsightBatchService
from multisigcore.hierarchy import MasterKey
from .branch import Branch, AccountPubkeys
from .recovery import CachedRecovery
from .batch import Batch
import json
from pycoin.encoding import EncodingError
try:
	from termcolor import colored
except ImportError:
	def colored(text, color=None): print text


__all__ = ['address', 'create', 'validate', 'cosign', 'broadcast', 'ScriptInputError']

class ScriptInputError(Exception):
	pass


def __get_insight(url):
	insight = InsightBatchService(url)
	try:
		insight.get_blockchain_tip()
	except Exception:
		raise ScriptInputError('Insight node at %s not reachable' % url)
	return insight


def __parse_key_sources(key_sources_string, register=None):
	try:
		strings = key_sources_string.split(',')
		return [AccountPubkeys.parse_string_to_account_key_source(string, register_oracle_accounts_file=register) for string in strings]
	except ValueError, err:
		raise ScriptInputError(err.message)


def __get_template(string):
	return getattr(Branch, '%s_account' % string)


def __check_source_strings(args):
	def check_cc_last(sources_str):
		for source_str in sources_str.split(',')[:-1]:
			if 'digitaloracle' in source_str:
				raise ScriptInputError('CryptoCorp API always has to be the last account key source\nChange sources order in --origin or --destination')
	if args.origin != args.destination and 'digitaloracle' in args.destination and not args.register:
		raise ScriptInputError('CryptoCorp API in destination branch but missing --register\nUse --register samples/account-registrations.json')
	check_cc_last(args.destination)
	check_cc_last(args.origin)


def __add_known_accounts(cached_recovery, known_accounts_file):
	with open(known_accounts_file) as fp:
		known_accounts = json.load(fp)
	for account_number, indexes in known_accounts.items():
		if indexes is not None and 'external_leafs' in indexes and 'internal_leafs' in indexes:
			cached_recovery.add_known_account(account_number, external_leafs=indexes['external_leafs'], internal_leafs=indexes['internal_leafs'])
		else:
			cached_recovery.add_known_account(account_number)


############  create, cosign, broadcast methods below  ###########################################


def address(args):
	"""Will return address of specified path in a branch. Used to manyally cross-check that you are working on correct branch."""
	#insight = __get_insight(args.insight)
	origin_key_sources = __parse_key_sources(args.origin)
	origin_branch = Branch(origin_key_sources, account_template=__get_template(args.origin_template), provider=None)
	path = args.path.split('/')
	if len(path) != 3 or sum([number.isdigit() for number in path]) != 3:
		print "! --path must be in format 0/0/0, digits only"
	else:
		path = [int(digit) for digit in path]
		account = origin_branch.account(int(path[0]))
		print "Account %s, address %s/%s: %s" % (path[0], path[1], path[2], account.address(path[2], change=bool(path[1])))



def create(args):
	insight = __get_insight(args.insight)
	__check_source_strings(args)

	# setup
	origin_key_sources = __parse_key_sources(args.origin)
	origin_branch = Branch(origin_key_sources, account_template=__get_template(args.origin_template), provider=insight)
	destination_key_sources = __parse_key_sources(args.destination, register=args.register)
	destination_branch = Branch(destination_key_sources, account_template=__get_template(args.destination_template), provider=insight)
	cached_recovery = CachedRecovery(origin_branch, destination_branch, provider=insight)
	if args.accounts:
		__add_known_accounts(cached_recovery, args.accounts)

	# recovery
	cached_recovery.recover_origin_accounts()
	cached_recovery.recover_destination_accounts()
	cached_recovery.create_and_sign_txs()
	print "Total to recover in this branch: %d" % cached_recovery.total_to_recover
	if cached_recovery.total_to_recover:
		cached_recovery.export_to_batch(args.save)

def validate(args):
	try:
		insight = __get_insight(args.insight)
	except ScriptInputError:
		raw_input("Insight node at " + args.insight + " not reachable. You can start this script again with --insight SOME_URL. Hit ENTER to continue with offline validation, or CTRL+Z to exit...")
		insight = None
	print ""

	try:
		batch = Batch.from_file(args.load)
		batch.validate(provider=insight)
		error = None
	except ValueError as err:
		print "Validation failed", err
		error = err

	print "   ____"
	print "  |"
	print "  |  Valid                : ", "False, with error: " + str(error) if error else 'True'
	print "  |  Transactions         : ", len(batch.batchable_txs)
	print "  |  Merkle root (calc)   : ", batch.build_merkle_root()
	print "  |  Merkle root (header) : ", batch.merkle_root
	print "  |  Total out            : ", batch.total_out, "satoshi", "-",batch.total_out/(100.0 * 10**6), "BTC"
	if not error and insight:
			print "  |  Total in             : ", batch.total_in, "satoshi", "-",batch.total_in/(100.0 * 10**6), "BTC"
			print "  |  Total fee            : ", batch.total_fee, "satoshi", "-",batch.total_fee/(100.0 * 10**6), "BTC"
			print "  |  Fee Percent          : ", batch.total_fee * 100.00 / batch.total_out
	print "  |____"
	print ""


def cosign(args):
	try:
		backup_mpk = MasterKey.from_key(args.private)
	except EncodingError:
		backup_mpk = MasterKey.from_seed_hex(args.private)
	batch = Batch.from_file(args.load)
	batch.validate()  # todo - validation
	original_merkle_root = batch.merkle_root
	batch.sign(master_private_key=backup_mpk)
	if batch.merkle_root != original_merkle_root:
		batch.to_file(args.save)
	else:
		print "! All signatures failed: wrong private key used, or malformed batch"


def broadcast(args):
	insight = __get_insight(args.insight)
	batch = Batch.from_file(args.load)
	batch.validate()  # todo - validation
	batch.broadcast(provider=insight)
