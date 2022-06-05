# -*- coding: utf-8 -*-
# @Version : 0.01
# @Author  : Mookim
# @File    : logger.py

import logging

logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
logger = logging.getLogger('easy_web3')