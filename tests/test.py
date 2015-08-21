#!/usr/bin/python2.7

# This is a simplified test of overall recovery including propagation on btc network.
# First run will create a test seed. The seed is created in a very insecure way, stored plain in a file.
# Never use this seed for anything other than testing. Deposit small amounts.

# The result of running this script should be that funds on deposit address are moved to the same address, less fees.

# usage:
# ./test.py http://address-of-your-insight-node:4001/

import random
import subprocess
import sys
from multisigcore.hierarchy import MasterKey
from pycoin.key.validate import is_address_valid
from multisigcore.providers.insight import InsightBatchService
from pycoin.serialize import h2b_rev
from urllib2 import HTTPError
import os

SEED_FILE = '_test-insecure.seed'
BATCH_FILE = '_test-batch.txs'
BATCH_FILE_SIGNED = '_test-batch-signed.txs'
INSIGHT = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:4001/'

try:
	os.remove(BATCH_FILE)
except:
	pass

try:
	os.remove(BATCH_FILE_SIGNED)
except:
	pass

insight_service = InsightBatchService(INSIGHT)

try:
	with open(SEED_FILE, 'r') as fp:
		insecure_seed_base = fp.read().strip()
except IOError:
	insecure_seed_base = ''.join([random.choice('0123456789abcdef') for i in range(0, 128)])  # please do not use this in production or you'll lose your coins
	with open(SEED_FILE, 'w') as fp:
		fp.write(insecure_seed_base)

def rotate(string, times=1):
	for i in range(0, times):
		letters = list(string)
		letters.append(letters.pop(0))
		string = ''.join(letters)
	return string


# creating seeds
seeds_hex = [insecure_seed_base, rotate(insecure_seed_base, 1), rotate(insecure_seed_base, 2), rotate(insecure_seed_base, 3)]
xpubs = [str(MasterKey.from_seed_hex(seed_hex).hwif()) for seed_hex in seeds_hex]


# getting first addresss, making sure funds are on it
process = subprocess.Popen([
	'python', './recovery', 'address',
	'--origin', '%s,%s,%s' % (seeds_hex[1], xpubs[2], xpubs[3]),
	'--path', '0/0/0',
], stdout=subprocess.PIPE)
process.wait()
deposit_address = process.communicate()[0].strip()[-34:]
print "[test] Working with testing address", deposit_address
assert is_address_valid(deposit_address)
if not insight_service.spendables_for_address(deposit_address):
	print "[test] No coins on target address to recover. Please deposit a small amount."
	exit(0)

print "\n\n[test] Creating batch"
# creating a batch
process = subprocess.Popen([
	'python', './recovery', 'create',
	'--origin', '%s,%s,%s' % (seeds_hex[1], xpubs[2], xpubs[3]),
	'--destination', '%s,%s,%s' % (seeds_hex[1], xpubs[2], xpubs[3]),
	'--insight', INSIGHT,
	'--save', BATCH_FILE,
])
process.wait()


print "\n\n[test] Adding second signature", BATCH_FILE
process = subprocess.Popen([
	'python', './recovery', 'cosign',
	'--load', BATCH_FILE,
	'--private', seeds_hex[2],
	'--save', BATCH_FILE_SIGNED,
])
process.wait()

# broadcasting
print "\n\n[test] Broadcasting", BATCH_FILE
process = subprocess.Popen([
	'python', './recovery', 'broadcast',
	'--load', BATCH_FILE_SIGNED,
	'--insight', INSIGHT,
], stdout=subprocess.PIPE)
process.wait()
stdout, stderr = process.communicate()
print stdout
if stderr:
	print stderr
else:
	last_line = stdout.strip().split('\n')[-1]
	try:
		_, txhash, bytes = last_line.split(' ')
	except:
		print "\n[test] no tx propagated"
		exit(1)
	print "\n\n[test] waiting for new tx to show in bitcoin mempool:",
	while True:
		try:
			found_tx = insight_service.get_tx(h2b_rev(txhash))
			break
		except HTTPError:
			print '.',
	print 'found.', found_tx, '\n\n', '[test] Coins successfuly moved'



