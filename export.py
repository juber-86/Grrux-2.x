#!/usr/bin/env python3


"""Utilities for the NEGra Export format.
"""


import tempfile


from discodop.treebank import NegraCorpusReader
from discodop.treebanktransforms import transform


def read_string(export_string, append_func=True):
    """Parses a string into trees.
    """
    with tempfile.NamedTemporaryFile() as f:
        f.write(export_string.encode('UTF-8'))
        f.flush()
        corpus = NegraCorpusReader(f.name)
        for key, item in corpus.itertrees():
            sent = item.sent.copy()
            if append_func:
                transform(item.tree, sent, ('APPEND-FUNC',))
            yield (key, item.tree, item.sent, item.comment)


def read_file(path):
    corpus = NegraCorpusReader(path)
    for key, item in corpus.itertrees():
        sent = item.sent.copy()
        transform(item.tree, sent, ('APPEND-FUNC',))
        yield (key, item.tree, item.sent, item.comment)


def blocks(f):
    """Splits export file contents into single-tree blocks.
    """
    block = []
    for line in f:
        if line.startswith('%% '):
            continue
        block.append(line)
        if line.startswith('#EOS '):
            yield ''.join(block)
            block = []
    if block:
        yield ''.join(block)


def str2sent(export_string):
    for line in export_string.splitlines():
        if not line.startswith('#'):
            yield line.split('\t')[0]
