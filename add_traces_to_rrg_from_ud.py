# this script takes an rrg-tree and a corresponding ud-tree and add traces to rrg-trees
# the script is similar to recovery of deep syntactic roles described in Ribeyre et al. 2014

from discodop import treebank, treetransforms

import re


""" make a list of children in the dependency tree """
def make_child_list(tree):
    child_list = []
    agenda = list(tree.children)
    while agenda:
        ch = agenda.pop()
        if not ch or len(ch.children) > 0:
            agenda.extend(list(ch.children))
            child_list.append(ch)
        else:
            child_list.append(ch)
    child_list.append(tree)
    return child_list


def find_parent(ch, ch_list):
    for x in ch_list:
        try:
            if ch in x.children:
                return x
        except:
            pass


def find_siblings_deprels(ch, ch_list):
    ch_parent = find_parent(ch, ch_list)
    return [x.token['deprel'] for x in ch_parent.children if x != ch]


def readFile(path):
    sentences = []
    sentence = []
    for line in open(path):
        line = line.strip()
        if not line:
            if len(sentence) > 0:
                sentences.append(sentence)
                sentence = []
        else:
            word = [x.strip() for x in line.strip().split("\t")]
            sentence.append(word)
    if len(sentence) > 0:
        sentences.append(sentence)
    print("number of sents: ", len(sentences))
    return sentences


def only_empty_nodes(node):
    node_length = len(node)
    empty_els = []
    for x in node:
        if re.match(r'.*(-NONE- [0-9]+).*', str(x)):
            empty_els.append(x)
    if len(empty_els) == node_length:
        return True


def find_t_trace_pairs_in_ptb_tree(item):

    lst_of_trace_idxs = []

    for stree in item.tree.subtrees():
        if len(stree) == 1 and not isinstance(stree[0], int) and stree[0].label == '-NONE-' and '*T*' in item.sent[stree.leaves()[0]]:
            t_trace = item.sent[stree.leaves()[0]]
            #print('T TRACE', t_trace)
            lst_of_trace_idxs.append(item.sent[stree.leaves()[0]].split('-')[-1])
            idx = stree.leaves()[0]
            if only_empty_nodes(stree.parent):
                stree.parent.parent.label = stree.parent.parent.label + '-' + t_trace
            else:
                stree.parent.label = stree.parent.label + '-' + t_trace
            treetransforms.removeemptynodes(item.tree, item.sent)


    trace_dict = {}
    for s in item.tree.subtrees():
        if re.match(r'.*(-[0-9]+).*', s.label):
            if s.label.split('-')[-1] in lst_of_trace_idxs and not '-TPC-' in s.label:
                if s.label.split('-')[-1] not in trace_dict:
                    trace_dict[s.label.split('-')[-1]] = [s.leaves()]
                else:
                    trace_dict[s.label.split('-')[-1]].append(s.leaves())

    for k, v in list(trace_dict.items()):
        if len(v) == 1:
            trace_dict.pop(k)
        elif abs(min(v[1])-max(v[0])) in [1,0]:
            trace_dict.pop(k)
        elif v[1][0] in v[0]:
            trace_dict.pop(k)

    return trace_dict
#


def test_t_traces_compare_to_ptb(trace_tuples, trace_dict_ptb):
    if len(trace_tuples) == 0 and len(trace_dict_ptb) == 0:
        return True
    if len(trace_tuples) == len(trace_dict_ptb) == 1:
        for k, v in trace_dict_ptb.items():
            if trace_tuples[0][0] in v[0] and trace_tuples[0][1] in v[1]:
                return True
    if len(trace_tuples) != len(trace_dict_ptb):
        return False
    else:
        return False

def create_tpls_with_traces(ch_list):
    lst_of_tokens_to_mark_traces = []
    t = 1
    for ch in ch_list:
        ch_parent = find_parent(ch, ch_list)
        if ch.token['deprel'] in ['xcomp'] and not ch.token['upostag'] in ['JJ']:

            if 'dobj' in find_siblings_deprels(ch, ch_list) or 'obj' in find_siblings_deprels(ch, ch_list):
                for x in ch_parent.children:
                    if x.token['deprel'] in ['dobj', 'obj'] \
                            and (x.token['upostag'][0].lower() == 'w'
                                 or x.token['upostag'].lower() in ['in']
                                or x.token['form'].lower() in ['what', 'which', 'that', 'who', 'whom']):
                        tpl = (x.token['id'] - 1, ch.token['id'] - 1, t)
                        lst_of_tokens_to_mark_traces.append(tpl)

            elif ('w' in [el[0].lower() for el in [k.token['upostag'] for k in ch_parent.children]]
                and not ('dobj' in find_siblings_deprels(ch, ch_list)) or 'obj' in find_siblings_deprels(ch, ch_list)):
                for x in ch_parent.children:
                    if 'w' in x.token['upostag'][0].lower() and not 'subj' in x.token['deprel']:
                        tpl = (x.token['id'] - 1, ch.token['id'] - 1, t)
                        lst_of_tokens_to_mark_traces.append(tpl)


        if ch.token['deprel'] in ['ccomp']:
            for x in ch_parent.children:
                if x.token['deprel'] in ['dobj', 'obj'] \
                        and (x.token['upostag'][0].lower() == 'w'
                             or x.token['upostag'].lower() in ['in']
                            or x.token['form'].lower() in ['what', 'which', 'that', 'who', 'whom', 'where', 'when', 'why', 'how']):
                    tpl = (x.token['id'] - 1, ch.token['id'] - 1, t)
                    lst_of_tokens_to_mark_traces.append(tpl)

        if ch.token['deprel'] in ['advcl', 'acl:relcl', 'acl']:
            for x in ch.children:
                if (x.token['form'].lower() in ['what', 'which', 'who', 'whom', 'where', 'when', 'why', 'how']
                    and abs(x.token['id'] - ch.token['id']) > 5):
                    tpl = (x.token['id'] - 1, ch.token['id'] - 1, t)
                    lst_of_tokens_to_mark_traces.append(tpl)

        t = t + 1

    number_of_dependent_node_pairs = len(lst_of_tokens_to_mark_traces)

    new_lst_of_tokens_to_mark_trees = []
    p = 1
    while p <= number_of_dependent_node_pairs:
        for node_pair in lst_of_tokens_to_mark_traces:
            new_node_pair = (node_pair[0], node_pair[1], p)
            new_lst_of_tokens_to_mark_trees.append(new_node_pair)
            p += 1

    new_lst_of_tokens_to_mark_trees = [x for x in new_lst_of_tokens_to_mark_trees if abs(x[1] - x[0]) > 2]

    return new_lst_of_tokens_to_mark_trees


def add_traces_to_rrg(roottree, rrg_export_tree, rrg_export_sent):

    ch_list = []

    #roottree[0].print_tree()
    child_list = make_child_list(roottree)
    ch_list.extend(child_list)

    lst_of_tokens = create_tpls_with_traces(child_list)

    item, sent = rrg_export_tree, rrg_export_sent
    tree_copy = item.copy(deep=True) # make a copy of the tree to not change the original one
    assert len(make_child_list(roottree)) == len(sent)

    for tp in lst_of_tokens:
        l1 = tp[0]
        l2 = tp[1]
        idx = tp[2]
        for x in tree_copy.subtrees():
            if len(x.leaves()) == 1 and x.leaves()[0] == l1 and x.label.startswith('NP') or x.label in ['ADVP-WH']:
                x.label = x.label + '[PREDID=%s]' % (str(idx))
            elif len(x.leaves()) == 1 and x.leaves()[0] == l1 and x.label in ['N-PROP', 'PRO-WH']:
                if len(x.parent) > 1:
                    x.parent.label = x.parent.label + '[PREDID=%s]' % (str(idx))

            if len(x.leaves()) == 1 and x.leaves()[0] == l2 and x.label in ['NUC']:
                x.label = x.label + '[NUCID=%s]' % (str(idx))
            elif len(x.leaves()) == 1 and x.leaves()[0] == l2 and x.label == 'V':
                if len(x.parent) > 1:
                    x.parent.label = x.parent.label + '[NUCID=%s]' % (str(idx))
            elif len(x.leaves()) == 1 and x.leaves()[0] == l2 and x.label == 'N':
                if len(x.parent) == 1 and x.parent.label in ['NUC_N']:
                    x.parent.label = x.parent.label + '[NUCID=%s]' % (str(idx))

    return tree_copy




