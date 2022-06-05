# -*- coding: utf-8 -*-
# @Version : 0.01
# @Author  : Mookim
# @File    : w3_provider.py

import os
import json
import time
import random
import eth_abi

from web3 import Web3
from base64 import *
from easy_web3.tools.utils import *
from easy_web3.utils.logger import logger


class W3_Provider():
    def __init__(self, rpc:str, private_key:str):
        os.makedirs("/tmp", exist_ok=True)
        if os.path.exists("/tmp/chainid.json"):
            _chainidcache = json.load(open("/tmp/chainid.json"))
        else:
            _chainidcache = {}

        w3 = Web3(Web3.HTTPProvider(rpc))
        if rpc not in _chainidcache:
            logger.info("get chain id...", flush=True, end="")
            starttime = time.time()
            chain_id = w3.eth.chain_id
            logger.info("ok, latency: %.2f"%(1000*(time.time()-starttime)))
            _chainidcache[rpc] = chain_id
            json.dump(_chainidcache, open("/tmp/chainid.json", "w"))
        else:
            chain_id = _chainidcache[rpc]
        addr = w3.eth.account.privateKeyToAccount(private_key).address
        logger.info("my address:", addr)

        self.chain_id = chain_id
        self.rpc = rpc
        self.w3 = w3
        self.private_key = private_key
        self.addr = addr

    def make_tx(self, to, data, nonce=None, gasprice=None, needstx=False, gaslimit=2000000, sendamount=None):
        if nonce is None:
            nonce = self.w3.eth.getTransactionCount(self.addr)
        if not gasprice:
            suggest = self.w3.eth.gasPrice
            gasprice = min(suggest + random.randint(1,100), 5*10**9)
        logger.info("nonce:", nonce, "gasprice:", "%.2f"%(gasprice/10**9))
        tx = dict(nonce=nonce, gasPrice=gasprice, gas=gaslimit, to=to, value=sendamount if sendamount else 0, data=data, chainId=self.chain_id)
        stx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        if needstx:
            return stx.rawTransaction
        txid = "0x"+b16encode(self.w3.eth.sendRawTransaction(stx.rawTransaction)).decode().lower()
        return txid

    def wait_tx(self, txhash, _times=50):
        times = _times
        logger.info("wait for tx", txhash)
        while times>0:
            if times!=_times:
                time.sleep(1)
            times -= 1
            try:
                tx = self.w3.eth.getTransactionReceipt(txhash)
                if tx['blockNumber']:
                    if tx.status==1:
                        logger.info("success in block", tx.blockNumber)
                        time.sleep(3)
                    else:
                        logger.warning("failed:", txhash)
                    return tx
            except:
                continue
        logger.error("[timeout]", txhash)
        raise Exception("waittx timeout")

    def approve(self, token, router, gasprice=None):
        token = self.w3.toChecksumAddress(token)
        return self.make_tx(to=token, 
                            data="0x"+function_hash("approve(address,uint256)")+toarg(router)+toarg(2**256-1),
                            gasprice=gasprice)
        
    def swapExactTokensForETH(self, endpoint, router, token, wnative, amount, slippage=1, nonce=None, gasprice=None):
        path = [token, wnative]
        expectedout = int(self.get_amounts_out(endpoint, router, amount, path) * (100 - slippage) / 100)
        logger.info("expected output:", expectedout/10**18)
        data = function_hash("swapExactTokensForETH(uint256,uint256,address[],address,uint256)")
        data += b16encode(eth_abi.encode_abi(["uint256","uint256","address[]","address","uint256"],
                         [amount, expectedout, path, self.addr, int(time.time())+86400])).lower().decode()
        return self.make_tx(to=router, data=data, nonce=nonce, gasprice=gasprice)

    def getAmountsOut(self, endpoint, router, amountIn, path):
        x = callfunction(endpoint, router, "getAmountsOut(uint256,address[])", 
            b16encode(eth_abi.encode_abi(["uint256","address[]"], [amountIn, path])).lower().decode(),
        "latest", False)
        amounts = eth_abi.decode_abi(["uint256[]"], b16decode(x[2:].upper()))[0]
        return amounts[-1]
