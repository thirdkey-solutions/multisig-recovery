#!/usr/bin/python

from recovery.recovery import CachedRecovery
from recovery.branch import Branch, OracleAccountPubkeys
from recovery.batch import Batch
from multisigcore.providers.insight import InsightBatchService
from multisigcore.hierarchy import ElectrumMasterKey, MasterKey
insight = InsightBatchService('http://127.0.0.1:4001/')


def create_and_sign_example():  # 1: original branch, destination branch, recovery + signing + export
	original_account_key_sources = [  # test local seed, test recovery key, cryptocorp sandbox api
		MasterKey.from_seed_hex('54b426b3e676649e8bfd66a2943f56fe74da2d2c0934d78db3a87dae44ed8d159e29ea93f6f33550a767c228786e75d020753575733bcf336943f7fa4ecfd37f'),
		ElectrumMasterKey.from_key('xpub69mdgvyDG2wbxwFTDhb6ghQ5Dgsdk1zGhxHPAq3C76XBbZCa4UJZZj3Ew7hLGCGvuxy4hseoWbj9KNoHzN1jZUovLMKP3rHThyWHZxKu5cA'),
		OracleAccountPubkeys('https://s.digitaloracle.co'),
	]
	destination_account_key_sources = original_account_key_sources  # todo - hack until we can create a new branch from scratch using CC API

	original_branch = Branch(original_account_key_sources, Branch.bitoasis_v1_account, provider=insight)
	destination_branch = Branch(destination_account_key_sources, Branch.bitoasis_v1_account, provider=insight)
	cached_recovery = CachedRecovery(original_branch, destination_branch, provider=insight)
	cached_recovery.add_known_account(1, external_leafs=[0], internal_leafs=[])  # funded account
	#cached_recovery.add_known_account(1, external_leafs=range(10), internal_leafs=range(3))  # funded account
	#cached_recovery.add_known_account(2, external_leafs=range(0, 3), internal_leafs=range(0, 1))  # empty account
	#cached_recovery.add_known_account(3, external_leafs=range(0, 3), internal_leafs=range(0, 1))  # not existing account
	cached_recovery.recover_original_accounts()
	cached_recovery.recover_destination_accounts()
	cached_recovery.create_and_sign_txs()
	cached_recovery.export_to_batch('batch.data')


def cosign_example():  # 2: import + validation + signing + export
	backup_mpk = MasterKey.from_seed_hex('5e3db9f73124fde2f91484872776f878f5256a87ba72c1f515e7f11d46922d838a2f0c9245d32224f302cd9fb6760fb779bc1efbe681a2ad74be819d5a648b70')
	batch = Batch.from_file('batch.data')
	batch.validate()  # todo - validation
	batch.sign(master_private_key=backup_mpk)  # todo - signing
	batch.to_file('batch_signed.data')


def broadcast_example():  # 3: import + validation + broadcasting
	batch = Batch.from_file('batch_signed.data')
	batch.validate()  # todo - validation
	batch.broadcast(provider=insight)  # todo - broadcasting


create_and_sign_example()
cosign_example()
broadcast_example()








# >>> from multisigcore.hierarchy import MasterKey
# >>> MasterKey.from_seed_hex('54b426b3e676649e8bfd66a2943f56fe74da2d2c0934d78db3a87dae44ed8d159e29ea93f6f33550a767c228786e75d020753575733bcf336943f7fa4ecfd37f').hwif(as_private=False)
# u'xpub661MyMwAqRbcGHE4FUEFv6KNBGpNudnQ3NRai8sRg6oF3Xnu746S6hE4S2SdoH8jdJHzSXiEndHizu5TDfqDWYHJXBxprH9xKskxSKvpxJw'
