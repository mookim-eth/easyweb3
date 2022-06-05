# -*- coding: utf-8 -*-
# @Version : 0.01
# @Author  : mookim.eth
# @File    : exception.py

class NoBlock(Exception):
    def __init__(self, text):
        self.text = text