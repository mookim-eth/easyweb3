# -*- coding: utf-8 -*-
# @Version : 0.01
# @Author  : mookim.eth
# @File    : rpc.py

import random

from sess import sess
from easy_web3.tools.endpoint_provider import Endpoint_Provider

RPCS = {i["chainId"]:i["rpc"] for i in sess.get("https://chainid.network/chains.json").json()}
extendRPCS = {int(k): v for k,v in sess.get("https://raw.githubusercontent.com/DefiLlama/chainlist/main/constants/extraRpcs.json").json().items()}
for chainid, rpcs in RPCS.items():
    newrpcs = rpcs
    if chainid in extendRPCS and extendRPCS[chainid].get("rpcs"):
        newrpcs.extend(extendRPCS[chainid]["rpcs"])
    RPCS[chainid] = [i for i in newrpcs if  i.startswith("http") and "${" not in i]
    
def chainid2provider(chainid):
    chainid = int(chainid)
    return Endpoint_Provider(random.sample(RPCS[chainid], 3))