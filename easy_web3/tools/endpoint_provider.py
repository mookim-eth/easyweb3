# -*- coding: utf-8 -*-
# @Version : 0.01
# @Author  : mookim.eth
# @File    : endpoint_provider.py

from asyncio.log import logger
import os
import traceback
import time

from typing import List
from functools import lru_cache
from .utils import *
from easy_web3.tools.exception import NoBlock
from easy_web3.config.constant import *

def Endpoint_Provider_retry_wrapper_allowexc(allowed_exceptions=None):
    def Endpoint_Provider_retry_wrapper(f):
        def do_f(self, *args, **kwargs):
            retrytimes = kwargs.get("retrytimes", 1)
            for i in range(retrytimes):
                j = 0
                for n in self.endpoints:
                    self.E = n
                    j += 1
                    try:
                        return f(self, *args, **kwargs)
                    except Exception as e:
                        if allowed_exceptions:
                            if any([isinstance(e, i) for i in allowed_exceptions]):
                                raise
                        if os.getenv("DEBUG_VERBOSE"):
                            traceback.print_exc()
                            logger.info("error:", e, "retry:", i, "bad_node:", n)
                        self.endpoints = self.endpoints[1:]+[self.endpoints[0]]
                logger.info("All failed, sleep 5")
                time.sleep(2)
        return do_f
    return Endpoint_Provider_retry_wrapper

Endpoint_Provider_retry_wrapper=Endpoint_Provider_retry_wrapper_allowexc()


class Endpoint_Provider:
    def __init__(self, endpoints):
        self.endpoints = endpoints
        self.E = endpoints[0]

    @Endpoint_Provider_retry_wrapper
    def batch_callfunction_decode(self, datalist:List, outtypes, height=None, needidx=False, timeout=10):
        if not height:
            height = "latest"
        if not isinstance(outtypes[0], list):
            outtypes = [outtypes]*len(datalist)
        data = batch_callfunction(self.E, datalist, height, timeout=timeout)
        res = []
        for i, item in data:
            if not item:
                res.append((i, None))
            else:
                if outtypes[i]==["raw"]:
                    d = item
                elif outtypes[i]==["hex"]:
                    d = int(item, 16)
                else:
                    d = eth_abi.decode_abi(outtypes[i], base64_decode(item))
                    if len(d)==1:
                        d = d[0]
                res.append((i, d))
        if needidx:
            return res
        else:
            return [i[1] for i in res]

    @Endpoint_Provider_retry_wrapper
    def erc20_balanceOf(self, contract, addr):
        return callfunction(self.E, contract, "balanceOf(address)", toarg(addr))

    @Endpoint_Provider_retry_wrapper
    def eth_getBalance(self, addr, height="latest"):
        return int(batch_callfunction(self.E, [["", "eth_getBalance", addr]], height)[0][1], 16)

    @Endpoint_Provider_retry_wrapper
    def eth_getBalance(self, addrs:List):
        return [int(i[1], 16) for i in batch_callfunction(self.E, [["", "eth_getBalance", addr] for addr in addrs], "latest")]

    @Endpoint_Provider_retry_wrapper
    def eth_getTransactionANDReceipt(self, txid):
        data = [{
            "id":1, "jsonrpc":"2.0",
            "method":"eth_getTransactionByHash",
            "params":[txid]
        }, {
            "id":2, "jsonrpc":"2.0",
            "method":"eth_getTransactionReceipt",
            "params":[txid]
        }, ]
        x = rpccall(self.E, data)
        assert x.status_code == 200, x.text
        if os.environ.get("DEBUG_VERBOSE"):
            logger.info(x.text)
        tx, receipt = x.json()
        tx = tx["result"]
        tx.update(receipt["result"])
        return tx
    
    @Endpoint_Provider_retry_wrapper
    def eth_getTransactionReceipt(self, txid):
        return simple_rpccall(self.E, "eth_getTransactionReceipt", [txid])

    @lru_cache()
    @Endpoint_Provider_retry_wrapper_allowexc([NoBlock])
    def eth_getBlockByNumber(self, height, needtx=True):
        if isinstance(height, int):
            height = hex(height)
        res = {}
        x = None
        try:
            x = rpccall(self.E, {"id":6,"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[height,needtx]})
            if os.environ.get("DEBUG_VERBOSE"):
                logger.info(self.E, x, x.text, height)
            res = x.json()["result"]
        except:
            if os.environ.get("DEBUG_VERBOSE", False):
                if x:
                    logger.info(x, x.text, self.E)
                traceback.print_exc()
            pass
        if not res or "transactions" not in res:
            if x:
                raise NoBlock(x.text)
            else:
                raise NoBlock("network failed, no x")
        return res

    @Endpoint_Provider_retry_wrapper
    def eth_getBlockByNumber(self):
        x1 = rpccall(self.E, {"id":1,"jsonrpc":"2.0","method":"eth_blockNumber","params":[]})
        x2 = rpccall(self.E, {"id":2,"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["latest",False]})
        if os.environ.get("DEBUG_VERBOSE", False):
            logger.info(x1.text)
            logger.info(x2.text)
        try:
            x1, x2 = x1.json(), x2.json()
        except:
            logger.info(x1.text)
            logger.info(x2.text)
            raise
        if x1["result"]<=x2["result"]["number"]:
            return x2["result"]
        x = rpccall(self.E, {"id":3,"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[x1["result"],False]})
        return x.json()["result"]

    @Endpoint_Provider_retry_wrapper
    def eth_getStorageAt(self, contract, index, height="latest", format="int"):
        if isinstance(index, int):
            index = hex(index)
        if isinstance(height, int):
            height = hex(height)
        data = {
            "id":1, "jsonrpc":"2.0",
            "method":"eth_getStorageAt",
            "params":[contract, index, height]
        }
        x = rpccall(self.E, data, timeout=5)
        err = None
        try:
            res = x.json()["result"]
        except Exception as e:
            err = e
        logger.info(x, x.text)
        if err:
            raise err
        if format == "int":
            return int(res, 16)
        elif format == "addr":
            return "0x"+res[-40:]
        else:
            return res

    def eth_sendRawTransaction(self, tx_hex):
        return simple_rpccall(self.E, "eth_sendRawTransaction", [tx_hex])


    @Endpoint_Provider_retry_wrapper
    def eth_getLogs(self, fromBlock, toBlock="latest", topics0=LOG_TRANSFER, moretopics=None, address=None, blockhash=None):
        topics = []
        if topics0:
            topics = [topics0]
            if moretopics:
                topics.extend(moretopics)
        param = {"fromBlock": to_hex(fromBlock), "toBlock": to_hex(toBlock), "topics": topics}
        if address is not None:
            param["address"] = address
        if blockhash is not None:
            param["blockhash"] = blockhash
        x = rpccall(self.E, {"method":"eth_getLogs", "params":[param]})
        return x.json()["result"]

    def eth_getTransactionCount(self, addr:str):
        return simple_rpccall(self.E, "eth_getTransactionCount", [addr, "latest"], returnint=True)

    def eth_getCode(self, addr:str):
        return simple_rpccall(self.E, "eth_getCode", [addr, "latest"])

    def eth_getBlockByNumber(self):
        x1 = rpccall(self.E, {"id":1,"jsonrpc":"2.0","method":"eth_blockNumber","params":[]}).json()
        x2 = rpccall(self.E, {"id":2,"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["latest",False]}).json()
        if x1["result"] <= x2["result"]["number"]:
            return x2["result"]
        x = rpccall(self.E, {"id":3,"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[x1["result"], False]})
        return x.json()["result"]

    def eth_chainId(self):
        return int(rpccall(self.E, {"method":"eth_chainId"}).json()["result"], 16)

    def get_allowance(self, token, router, myaddr):
        return callfunction(self.E, token, "allowance(address,address)", toarg(myaddr)+toarg(router))

    def eth_getBalance(self, address:str, height:str="latest"):
        return int(rpccall(self.E, {"method":"eth_getBalance", "params":[address, to_hex(height)]}).json()["result"], 16)

    def eth_accounts(self):
        return rpccall(self.E, {"method":"eth_accounts"}).json()["result"]

    def get_implemention(self, address:str, implementation_slot:str="0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"):
        return self.eth_getStorageAt(address, implementation_slot, "latest", "addr")