"""RRG clause linkage tools
"""


from discodop.tree import ParentedTree


NUC = 'NUC'
CORE = 'CORE'
CLAUSE = 'CLAUSE'
SENTENCE = 'SENTENCE'


LINKABLES = (SENTENCE, CLAUSE, CORE, NUC)


class ClauseLinkageError(Exception):
    pass


def match(tree_label, layer):
    return tree_label.split('-')[0] == layer


def split_sentence(sentence1: ParentedTree) -> (ParentedTree, [ParentedTree], [ParentedTree]):
    sentence2 = None
    clause = None
    cosubordinated = []
    subordinated = []
    for child in sentence1:
        if clause is None and match(child.label, 'CLAUSE'):
            clause = child
        elif sentence2 is None and match(child.label, 'SENTENCE'):
            sentence2 = child
        else:
            subordinated.append(child)
    if clause is None:
        if sentence2 is None:
            raise ClauseLinkageError('CLAUSE not found in {}'.format(sentence1))
        cosubordinated = subordinated
        subordinated = []
        for child in sentence2:
            if clause is None and match(child.label, 'CLAUSE'):
                clause = child
            else:
                subordinated.append(child)
        if clause is None:
            raise ClauseLinkageError('CLAUSE not found in {}'.format(sentence1))
    elif sentence2 is not None:
        subordinated.append(sentence2)
    return clause, cosubordinated, subordinated


def split_clause(clause1: ParentedTree) -> (ParentedTree, [ParentedTree], [ParentedTree]):
    clause2 = None
    core = None
    cosubordinated = []
    subordinated = []
    for child in clause1:
        if core is None and match(child.label, 'CORE'):
            core = child
        elif clause2 is None and match(child.label, 'CLAUSE'):
            clause2 = child
        else:
            subordinated.append(child)
    if core is None:
        if clause2 is None:
            raise ClauseLinkageError('CORE not found in {}'.format(clause1))
        cosubordinated = subordinated
        subordinated = []
        for child in clause2:
            if core is None and match(child.label, 'CORE'):
                core = child
            else:
                subordinated.append(child)
        if core is None:
            raise ClauseLinkageError('CORE not found in {}'.format(clause1))
    elif clause2 is not None:
        subordinated.append(clause2)
    return core, cosubordinated, subordinated


def split_core(core1: ParentedTree) -> (ParentedTree, [ParentedTree], [ParentedTree]):
    core2 = None
    nuc = None
    cosubordinated = []
    subordinated = []
    for child in core1:
        if nuc is None and match(child.label, 'NUC'):
            nuc = child
        elif core2 is None and match(child.label, 'CORE'):
            core2 = child
        else:
            subordinated.append(child)
    if nuc is None:
        if core2 is None:
            raise ClauseLinkageError('NUC not found in {}'.format(core1))
        cosubordinated = subordinated
        subordinated = []
        for child in core2:
            if nuc is None and match(child.label, 'NUC'):
                nuc = child
            else:
                subordinated.append(child)
        if nuc is None:
            raise ClauseLinkageError('NUC not found in {}'.format(core1))
    elif core2 is not None:
        subordinated.append(core2)
    return nuc, cosubordinated, subordinated


def clause_sub(sentence1: ParentedTree, sentence2: ParentedTree,
        clause1: ParentedTree, clause2: ParentedTree, core1: ParentedTree,
        core2: ParentedTree, nuc1: ParentedTree, nuc2: ParentedTree,
        guest: ParentedTree) -> None:
    if not match(guest.label, 'SENTENCE'):
        clause2.append(guest)
        return
    clause, cosubordinated, subordinated = split_sentence(guest)
    sentence1.extend(t.detach() for t in cosubordinated)
    sentence2.extend(t.detach() for t in subordinated)
    clause2.append(clause.detach())


def clause_cosub(sentence1: ParentedTree, sentence2: ParentedTree,
        clause1: ParentedTree, clause2: ParentedTree, core1: ParentedTree,
        core2: ParentedTree, nuc1: ParentedTree, nuc2: ParentedTree,
        guest: ParentedTree) -> None:
    if not match(guest.label, 'SENTENCE'):
        clause1.append(guest)
        return
    clause, cosubordinated, subordinated = split_sentence(guest)
    sentence1.extend(t.detach() for t in cosubordinated)
    sentence2.extend(t.detach() for t in subordinated)
    clause1.append(clause.detach())


def core_sub(sentence1: ParentedTree, sentence2: ParentedTree,
        clause1: ParentedTree, clause2: ParentedTree, core1: ParentedTree,
        core2: ParentedTree, nuc1: ParentedTree, nuc2: ParentedTree,
        guest: ParentedTree) -> None:
    if not match(guest.label, 'SENTENCE'):
        core2.append(guest)
        return
    clause, cosubordinated, subordinated = split_sentence(guest)
    sentence1.extend(t.detach() for t in cosubordinated)
    sentence2.extend(t.detach() for t in subordinated)
    core, cosubordinated, subordinated = split_clause(clause)
    clause1.extend(t.detach() for t in cosubordinated)
    clause2.extend(t.detach() for t in subordinated)
    core2.append(core.detach())


def core_cosub(sentence1: ParentedTree, sentence2: ParentedTree,
        clause1: ParentedTree, clause2: ParentedTree, core1: ParentedTree,
        core2: ParentedTree, nuc1: ParentedTree, nuc2: ParentedTree,
        guest: ParentedTree) -> None:
    if not match(guest.label, 'SENTENCE'):
        core1.append(guest)
        return
    clause, cosubordinated, subordinated = split_sentence(guest)
    sentence1.extend(t.detach() for t in cosubordinated)
    sentence2.extend(t.detach() for t in subordinated)
    core, cosubordinated, subordinated = split_clause(clause)
    clause1.extend(t.detach() for t in cosubordinated)
    clause2.extend(t.detach() for t in subordinated)
    core1.append(core.detach())


def core_coord(sentence1: ParentedTree, sentence2: ParentedTree,
        clause1: ParentedTree, clause2: ParentedTree, core1: ParentedTree,
        core2: ParentedTree, nuc1: ParentedTree, nuc2: ParentedTree,
        guest: ParentedTree) -> None:
    if not match(guest.label, 'SENTENCE'):
        core1.append(guest)
        return
    clause, cosubordinated, subordinated = split_sentence(guest)
    sentence1.extend(t.detach() for t in cosubordinated)
    sentence2.extend(t.detach() for t in subordinated)
    core, cosubordinated, subordinated = split_clause(clause)
    clause1.extend(t.detach() for t in cosubordinated)
    clause2.extend(t.detach() for t in subordinated)
    clause2.append(core.detach())
    

def nuc_cosub(sentence1: ParentedTree, sentence2: ParentedTree,
        clause1: ParentedTree, clause2: ParentedTree, core1: ParentedTree,
        core2: ParentedTree, nuc1: ParentedTree, nuc2: ParentedTree,
        guest: ParentedTree) -> None:
    #print('NUC-cosubordinating {} into {}'.format(guest, sentence1))
    if not match(guest.label, 'SENTENCE'):
        nuc1.append(guest)
        return
    clause, cosubordinated, subordinated = split_sentence(guest)
    #print('Clause: {}, cosubordinated: {}, subordinated: {}'.format((clause.label, sorted(clause.leaves())), [(c.label, sorted(c.leaves())) for c in cosubordinated], [(s.label, sorted(s.leaves())) for s in subordinated]))
    sentence1.extend(t.detach() for t in cosubordinated)
    sentence2.extend(t.detach() for t in subordinated)
    core, cosubordinated, subordinated = split_clause(clause)
    #print('Core: {}, cosubordinated: {}, subordinated: {}'.format((core.label, sorted(core.leaves())), [(c.label, sorted(c.leaves())) for c in cosubordinated], [(s.label, sorted(s.leaves())) for s in subordinated]))
    clause1.extend(t.detach() for t in cosubordinated)
    clause2.extend(t.detach() for t in subordinated)
    nuc, cosubordinated, subordinated = split_core(core)
    #print('Nucleus: {}, cosubordinated: {}, subordinated: {}'.format((nuc.label, sorted(nuc.leaves())), [(c.label, sorted(c.leaves())) for c in cosubordinated], [(s.label, sorted(s.leaves())) for s in subordinated]))
    core1.extend(t.detach() for t in cosubordinated)
    core2.extend(t.detach() for t in subordinated)
    nuc1.append(nuc.detach())


def add_punctuation(tree: ParentedTree, punctuation: [ParentedTree]) -> None:
    """Adds one or more punctuation tokens to tree.

    Punctuation is attached at the highest node that has more than one child,
    has a label starting with NUC, is a preterminal, or whose child is a
    preterminal.
    """
    if len(tree) > 1 or not isinstance(tree[0], ParentedTree) or \
            not any(match(tree[0].label, l) for l in LINKABLES):
        if not isinstance(tree[0],ParentedTree):
            if tree.label in ('A','ADV','N','P','Q'):
                new_root = ParentedTree('NUC_'+tree.label, [])
            else:
                # this should not happen (but sometimes does for PRT)
                new_root = ParentedTree('NUC', [])                
            new_root.append(tree)
            tree=new_root
        tree.extend(punctuation)
    else:
        add_punctuation(tree[0], punctuation)


def reduce_to(tree: ParentedTree, juncture: str):
    if tree.label == juncture:
        return tree.detach()
    if not any(match(tree[0].label, l) for l in LINKABLES):
        return tree
    if len(tree) > 1:
        return tree.detach()
    return reduce_to(tree[0], juncture)
