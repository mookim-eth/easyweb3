# -*- coding: utf-8 -*-
# @Version : 0.01
# @Author  : Moonkim
# @File    : utils.py

import eth_abi
import sys

from time import sleep
from functools import lru_cache
from Crypto.Hash import keccak
from base64 import *
from .sess import sess


def simple_rpccall(endpoint, method, params, returnint=False):
    data={"method":method, "params":params}
    x = rpccall(endpoint, data)
    assert x.status_code == 200, x.text
    res = x.json()["result"]
    if returnint:
        res = int(res,16)
    return res

def rpccall(endpoint, data, timeout=10):
    if isinstance(data, dict):
        data["jsonrpc"]="2.0"
        if "id" not in data:
            data["id"] = 1
        if "params" not in data:
            data["params"] = []
    x = sess.post(endpoint, json=data, timeout=timeout)
    sys.x = x
    return x

def sha3(s):
    if isinstance(s, str):
        assert all([i.lower() in "0123456789abcdef" for i in s])
        s = b64decode(s)
    return keccak.new(digest_bits=256).update(s).hexdigest()

def event_hash(s):
    return sha3(s.encode("utf-8"))

def function_hash(func_str):
    if func_str.startswith("0x") and len(func_str)==10:
        return func_str[2:]
    return event_hash(func_str)[:8]

def toarg(addr):
    if isinstance(addr, int):
        addr = hex(addr)
    if addr.startswith("0x"):
        addr = addr[2:]
    return addr.lower().rjust(64, "0")

def callfunction(endpoint, addr, func_str, args_str, blockid="latest", returnint=True, from_=None):
    func_str = func_str.replace(" ", "")
    try:
        height = hex(int(blockid))
    except:
        height = blockid
    data = {
        "id": 1, "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"data": "0x" + function_hash(func_str) + args_str, "to": addr, }, height]
    }
    if from_ is not None:
        data["params"][0]["from"] = from_
    x = rpccall(endpoint, data)
    try:
        res = x.json()["result"]
    except:
        print(x, x.request.body, x.text)
        raise
    if not returnint:
        return res
    else:
        return int(res, 16)


seenerrs = set()
def endpoint_broadcast(w, stx, ret=None):
    knownerrs = ["Non-hexadecimal digit found", "already known", "nonce too low", "Known transaction", "Too Many Requests", "insufficient funds for gas"]
    for i in range(5):
        try:
            txid = "0x"+b16encode(w.eth.sendRawTransaction(stx)).decode().lower()
            if ret is not None and "tx" not in ret:
                ret["tx"] = txid
                print(txid)
        except Exception as e:
            if "nonce too low" in str(e):
                return
            if any([i in str(e) for i in knownerrs]):
                pass
            else:
                if (w.provider.endpoint_uri, str(e)) not in seenerrs:
                    print(w.provider.endpoint_uri, e)
                    seenerrs.add((w.provider.endpoint_uri, str(e)) )
        sleep(1)
        if ret.get("done", False):
            return

def base64_decode(result_str):
    if isinstance(result_str, tuple) and len(result_str)==2 and isinstance(result_str[0], int):
        result_str = result_str[1]
    if result_str.startswith("0x"):
        result_str = result_str[2:]
        if len(result_str)%2!=0:
            result_str = "0"+result_str
    return b16decode(result_str.upper())

def ed(abi, calldata):
    return eth_abi.decode_abi(abi, base64_decode(calldata[10:]))

def ec(abi, calldata):
    return b16encode(eth_abi.encode_abi(abi, calldata)).decode().lower()

@lru_cache(10)
def debugtrace(endpoint, txhash):
    x = rpccall(endpoint, {"method":"debug_traceTransaction", "params":[txhash, {"enableMemory": True, "enableReturnData": True}]}, timeout=600)
    res = x.json()["result"]
    l = res['structLogs']
    for idx, item in enumerate(l):
        item["idx"] = idx
    return l

def to_int(text):
    if isinstance(text, int):
        return text
    if text.startswith("0x"):
        return int(text, 16)
    return int(text, 16)

def to_hex(i):
    if isinstance(i, str):
        return i
    return hex(i)

def safefilename(filename):
    for i in "\\/:*?\"<>|$":
        filename=filename.replace(i,"_")
    return filename

def batch_callfunction(end_point, datalist, height, timeout=10):
    data = []
    idx = 0
    for item in datalist:
        extra = {}
        if len(item)==3:
            addr, func_str, args_str = item
        else:
            addr, func_str, args_str, extra = item
        idx += 1
        if func_str == "eth_getStorageAt":
            if isinstance(args_str, int):
                args_str = hex(args_str)
            data.append({"id": idx, "jsonrpc":"2.0", "method":func_str,
                "params": [addr, args_str, height]
            })
        elif func_str.startswith("eth_"):
            data.append({"id": idx, "jsonrpc":"2.0", "method":func_str,
                "params": [args_str, height]
            })
        else:
            param = {"data": "0x"+function_hash(func_str)+args_str, "to": addr,}
            if extra.get("from", None):
                param["from"] = extra["from"]
            data.append({"id": idx, "jsonrpc":"2.0", "method":"eth_call",
                "params":[param, height]
            })
    x = rpccall(end_point, data, timeout=timeout)
    resjson = x.json()
    if not isinstance(resjson, list):
        resjson = [resjson]
    res = [(i["id"]-1,i.get("result", None)) for i in resjson]
    res.sort(key=lambda i:i[0])
    return res

def batch_callfunction_withblock(endpoint, datalist, timeout=50):
    data = []
    idx = -1
    for addr, func_str, args_str, height_str in datalist:
        idx += 1
        if func_str.startswith("eth_"):
            data.append({"id": idx, "jsonrpc":"2.0", "method":func_str,
                "params": [args_str, height_str]
            })
        else:
            data.append({"id": idx, "jsonrpc":"2.0", "method":"eth_call",
                "params":[{"data": "0x"+function_hash(func_str)+args_str, "to": addr,}, height_str]
            })
    x = rpccall(endpoint, data, timeout)
    res = [(i["id"],i.get("result", None)) for i in x.json()]
    return res