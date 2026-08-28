import hashlib


from discodop.treebanktransforms import transform
from discodop.treebank import NegraCorpusReader, incrementaltreereader
from discodop.tree import Tree
import itertools


def sha256(string):
    hasher = hashlib.sha256()
    hasher.update(string.encode('UTF-8'))
    return hasher.digest()


def is_preterminal(tree):
    return len(tree.children) == 1 and not isinstance(tree.children[0], Tree)


def preterminals(tree):
    yield from (s for s in tree.subtrees() if is_preterminal(s))


def blocks(f):
    """Splits file contents into blocks terminated by empty lines.
    """
    block = []
    for line in f:
        block.append(line)
        if line.splitlines() == ['']:
            yield ''.join(block)
            block = []
    if block:
        yield ''.join(block)


def conllstr2sent(conll_string):
    for line in conll_string.splitlines():
        if not line.startswith('#') and not line=="":
            yield line.split('\t')[1].replace(' ','_')


def ranges(iterable):
    """Make an iterator that returns consecutive keys and ranges from the iterable."""
    offset = 0
    for k, group in itertools.groupby(iterable):
        length = len(tuple(group))
        yield offset, offset + length, k
        offset += length