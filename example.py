#!/usr/bin/python

from recovery.recovery import CachedRecovery
from recovery.branch import Branch, OracleAccountPubkeys
from recovery.batch import Batch
from multisigcore.providers.insight import InsightBatchService
from multisigcore.hierarchy import ElectrumMasterKey, MasterKey
insight = InsightBatchService('http://127.0.0.1:4001/')


account_key_sources = [  # test local seed, test recovery key, cryptocorp sandbox api
	MasterKey.from_seed_hex('54b426b3e676649e8bfd66a2943f56fe74da2d2c0934d78db3a87dae44ed8d159e29ea93f6f33550a767c228786e75d020753575733bcf336943f7fa4ecfd37f'),
	ElectrumMasterKey.from_key('xpub69mdgvyDG2wbxwFTDhb6ghQ5Dgsdk1zGhxHPAq3C76XBbZCa4UJZZj3Ew7hLGCGvuxy4hseoWbj9KNoHzN1jZUovLMKP3rHThyWHZxKu5cA'),
	OracleAccountPubkeys('https://s.digitaloracle.co'),
]


# 1: branch + recovery + signing + export
branch = Branch(account_key_sources, Branch.bitoasis_v1_account)
cached_recovery = CachedRecovery(branch, provider=insight)
cached_recovery.add_known_account(1, external_leafs=range(0, 50), internal_leafs=range(0, 10))  # todo - cheating here. Add searching for accounts, gap limits
cached_recovery.recover_accounts()
cached_recovery.create_txs()  # todo - create txs
batch = cached_recovery.export_to_batch('batch.data', return_batch=True)
batch.sign(account_key_sources[0])  # todo - signing
batch.to_file('batch_halfsigned.data')


# 2: import + validation + signing + export
batch = Batch.from_file('batch_halfsigned.data')
batch.validate()  # todo - validation
batch.sign(master_private_key='=== recovery xprv ===')  # todo - signing
batch.to_file('batch_signed.data')


# 3: import + validation + broadcasting
batch = Batch.from_file('batch_signed.data')
batch.validate()  # todo - validation
batch.broadcast(provider=insight)  # todo - broadcasting
