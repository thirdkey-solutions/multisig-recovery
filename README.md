
PROTOTYPE - Branch migrations for multisig wallets

Currently needs https://github.com/bit-oasis/multisig-core/tree/softened version of `multisig-core`

 
```bash

	./recovery -h

    ./recovery create \
        --origin 54b426b3e676649e8bfd66a2943f56fe74da2d2c0934d78db3a87dae44ed8d159e29ea93f6f33550a767c228786e75d020753575733bcf336943f7fa4ecfdaaa,xpub69mdgvyDG2wbxwFTDhb6ghQ5Dgsdk1zGhxHPAq3C76XBbZCa4UJZZj3Ew7hLGCGvuxy4hseoWbj9KNoHzN1jZUovLMKP3rHThyWHZxKu5cA \
        --destination cccc26b3e676649e8bfd66a2943f56fe74da2d2c0934d78db3a87dae44ed8d159e29ea93f6f33550a767c228786e75d020753575733bcf336943f7fa4ecfbbbb,xpub69mdgvyDG2wbxwFTDhb6ghQ5Dgsdk1zGhxHPAq3C76XBbZCa4UJZZj3Ew7hLGCGvuxy4hseoWbj9KNoHzN1jZUovLMKP3rHThyWHZxKu5cA \
        --save test.txs

    ./recovery cosign \
        --load test.txs \
        --seed 5e3db9f73124fde2f91484872776f878f5256a87ba72c1f515e7f11d46922d838a2f0c9245d32224f302cd9fb6760fb779bc1efbe681a2ad74be819d5a648b70 \
        --save test-signed.txs

    ./recovery broadcast \
        --load test-signed.txs
```


```
	positional arguments:
	  {create,cosign,broadcast}

	optional arguments:
	  -h, --help            show this help message and exit
	  --load FILE           Load from batch file (cosign, broadcast)
	  --save FILE           Save to batch file (create, cosign)
	  --origin MKs          Original branch keys, comma separated (create)
	  --destination MKs     Destination branch keys, comma separated (create)
	  --accounts FILE       Use list of known account indexes. (create)
	  --insight URL         Default: http://127.0.0.1:4001/ (create, broadcast)
	  --template TYPE       Default: bip32 (create)
	  --seed SEED           Signing hex seed (cosign)
	  --register FILE       New accouts data file for CC API (create)

	./recovery create --origin <KS1,KS2,KS3> --destination <KS1,KS2,KS3> --save <FILE>
	./recovery cosign --load <FILE> --seed <SEED> --save <FILE>
	./recovery broadcast --load <FILE>

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
	 - samples/account-registrations.json : you will need to supply account personal information in this format to register
	        accounts on CryptoCorp for the new branch. Usage: --register samples/account-registrations.json
```
