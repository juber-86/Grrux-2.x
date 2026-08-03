"""ud2rrg.py - transform Universal Dependencies (UD) to RRG trees.

This script processes UD v1, see
http://universaldependencies.org/docsv1/u/dep/index.html for the dependency
relations.

Usage
-----

Paths are currently hard-coded, so just call:

    python3 ud2rrg.py
"""


### IMPORTS ###################################################################


import argparse
import export
import linkage
import logging
import math
import sys
import util
import copy


from conllu import parse_tree_incr
from discodop.eval import Evaluator, readparam, TreePairResult
from discodop.tree import ParentedTree, DrawTree, Tree, ptbunescape
from discodop.treebank import writeexporttree, NegraCorpusReader, FUNC
from discodop.treebanktransforms import transform as discodop_transform
from discodop.treetransforms import canonicalize, removeemptynodes
from verbnet import say_hyponyms, conjecture_hyponyms, care_hyponyms, consider_hyponyms, begin_hyponyms, sustain_hyponyms, stop_hyponyms
from add_traces_to_rrg_from_ud import *
from decimal import Decimal

### EXCEPTIONS ################################################################


class NotHandled(Exception):

    def __init__(self, udnode):
        message = 'subtree not handled ({})'.format(', '.join('{}: {}'.format(k, v) for k, v in udnode.token.items()))
        Exception.__init__(self, message)


### UD TREE HELPERS ###########################################################


# UD POS: PUNCT
def is_punctuation(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('``', ',', ':', '.', "''", '-LRB-', '$.', '$,','$(','$)','PUNCT',\
                                           '-RRB-', '-NONE-', '$','HYPH',
                                           'DELM')
    else:
        return udnode.token['upostag']=='PUNCT'

# UD POS: INTJ
def is_interjection(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('UH','ITJ')
    else:
        return udnode.token['upostag']=='INTJ'
        
        
# UD POS: PRT (and ADP for PTKVZ)
def is_particle(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in('RP','PTKVZ','PTKZU','PTKA','PTKNEG','PTKANT','APPO',
                                           # should CLITIC be here?
                                           'CLITIC')
    else:
        return udnode.token['upostag']=='PART'

# UD POS: PRT
def is_neg_particle(udnode,language):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('PTKNEG') or udnode.token['lemma']=='not' 
    else:
        return (language=='ru' and udnode.token['lemma'] in ('не','ни')) or (language=='fr' and udnode.token['lemma'] in ('ne','pas'))
    
# UD POS: DET (with feat det:predet)
def is_predeterminer(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] == 'PDT'
    else:
        return udnode.token['upostag']=='DET' and udnode.token['feats'] and 'det' in udnode.token['feats'] and udnode.token['feats']['det']=='predet' 
    
# UD POS: DET
def is_determiner(udnode):
    if(udnode.token['xpostag']):
        # ART: article, PPOSAT: possessive/personal, IS PIAT determiner or pronoun -> det seems to work more often
        return udnode.token['xpostag'] in ('DT','ART','PPOSAT','PIAT',
                                           'DET'        )
    else:
        return udnode.token['upostag']=='DET'

def is_neg_determiner(udnode):
    if(udnode.token['lemma']):
        return udnode.token['lemma'] in ('no','kein')
    else:
        return False
    
# UD POS: PRON (with feats PronType=Prs and Poss=Yes)
def is_possessive_pronoun(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] == 'PRP$'
    else:
        return udnode.token['upostag']=='PRON' and udnode.token['feats'] and 'PronType' in udnode.token['feats'] and udnode.token['feats']['PronType']=='Prs' and 'Poss' in udnode.token['feats'] and udnode.token['feats']['Poss']=='Yes'
    
# UD POS: NUM
def is_cardinal(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('CD','CARD',
                                           'NUM')
    else:
        return udnode.token['upostag']=='NUM'
    
# UD POS: PRON (?)
def is_existential_there(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] == 'EX'
    else:
        return False# udnode.token['upostag']=='PRON'
    
# UD POS: PRON (with feat PronType=Prs)
# also indefinite and demonstrative pronouns
def is_personal_pronoun(udnode,language):
    if(udnode.token['xpostag']):
        # PPER/PRF: personal, PDS: demonstrative, PIS 
        return udnode.token['xpostag'] in ('PRP','PPER','PRF','PIS',
                                           'PRO')
    else:
        return (udnode.token['upostag']=='PRON' and udnode.token['feats'] and 'PronType' in udnode.token['feats'] and udnode.token['feats']['PronType']=='Prs') or (language=='ru' and udnode.token['upostag']=='PRON' )
    # looks like Russian data does not have the PronType feature

def is_indef_pronoun(udnode):
    if(udnode.token['xpostag']):
        # PPER/PRF: personal, PDS: demonstrative, PIS
        # all DT except for this and that?
        #return udnode.token['xpostag'] in ('DT',) and udnode.token['lemma'] in ('anything','anyone','anybody','something','someone','everything','everyone','nothing','all')
        return udnode.token['xpostag'] in ('DT',) and (udnode.token['lemma'].startswith('any') or udnode.token['lemma'].startswith('some') or udnode.token['lemma'].startswith('every') or udnode.token['lemma'].startswith('no') or udnode.token['lemma'] in ('all','both','another','less','many','other','others','some'))
    else:
        return udnode.token['upostag']=='PRON' and udnode.token['feats'] and 'PronType' in udnode.token['feats'] and udnode.token['feats']['PronType']=='Ind'    

    
def is_dem_pronoun(udnode):
    if(udnode.token['xpostag']):
        # PPER/PRF: personal, PDS: demonstrative, PIS 
        return udnode.token['xpostag'] in ('PDS','PDAT','PIDAT')
    else:
        return udnode.token['upostag']=='PRON' and udnode.token['feats'] and 'PronType' in udnode.token['feats'] and udnode.token['feats']['PronType']=='Dem'    
    
# UD POS: PROPN
def is_proper_noun(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'].startswith('NNP') or udnode.token['xpostag'] in ('PROPN','FW','NE')
    else:
        return udnode.token['upostag']=='PROPN'
    
# UD POS: PRON (with feat PronType=Rel)
def is_wh_determiner(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] == 'WDT'
    else:
        return udnode.token['upostag']=='PRON' and udnode.token['feats'] and 'PronType' in udnode.token['feats'] and udnode.token['feats']['PronType']=='Int'


def is_rel_determiner(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('WDT',)
    else:
        return udnode.token['upostag']=='PRON' and udnode.token['feats'] and 'PronType' in udnode.token['feats'] and udnode.token['feats']['PronType']=='Rel'
    
# UD POS: PRON (with feat PronType=Int)
def is_wh_pronoun(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('WP$','PWS','PWAT')
    else:
        return udnode.token['upostag']=='PRON' and udnode.token['feats'] and 'PronType' in udnode.token['feats'] and udnode.token['feats']['PronType'] in ('Int',)

# UD POS: PRON (with feat PronType=Rel)
def is_rel_pronoun(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('WP','PRELS','PRELAT')
    else:
        return udnode.token['upostag']=='PRON' and udnode.token['feats'] and 'PronType' in udnode.token['feats'] and udnode.token['feats']['PronType'] in ('Rel',)

_ES_CLITIC_FORMS = ('me','te','se','le','les','lo','la','los','las','nos','os')

def is_clitic_pronoun(udnode,language):
    if (language=='fr' and udnode.token['upostag'] and udnode.token['upostag']=='PRON') and udnode.token['lemma'] in ('se','le','la','y','en','lui'):
        return True
    elif (language=='es' and udnode.token['upostag']=='PRON') and udnode.token['form'] and udnode.token['form'].lower() in _ES_CLITIC_FORMS:
        # Fallback sin MISC (RRGRole=AGX): pronombre atono dativo/acusativo.
        # 'se' tambien puede llegar por expl/expl:pv, con manejo propio que
        # esto no toca (deprel distinto).
        return True
    else:
        return False

def _es_conllu_analizado(udnode):
    """Fase L5 §1 (conciliación AGX) — ¿este .conllu lo inyectó gruxx con el
    canal MISC? (marca RRGAnalyzed=si en la raíz, ver
    aspect_classifier.misc_rrg.anotaciones_misc). Si es así, el MISC es la
    ÚNICA fuente de verdad para AGX: ud2rrg NO debe inventar nodos AGX por su
    cuenta (fallback is_clitic_pronoun) para clíticos que la Etapa 1 no marcó
    -- eso producía el patrón dominante de L4.5 'árbol con MÁS AGX que la LS'.
    Sin MISC (conllu crudo de terceros) el fallback se conserva intacto."""
    return bool((udnode.token.get('misc') or {}).get('RRGAnalyzed'))

def is_neg_pronoun(udnode,language):
    if (language=='fr' and udnode.token['upostag'] and udnode.token['upostag']=='PRON') and udnode.token['lemma'] in ('personne','rien'):
        return True
    else:
        return False

    
# UD POS??
def is_monetary_unit(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] == '$'
    else:
        return udnode.token['upostag']=='$'
    
# UD POS: PART
def is_possessive_ending(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] == 'POS'
    else:
        return udnode.token['upostag']=='PART'
    
# UD POS: ADP
def is_preposition(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('IN','APPR','APPRART','APZR',
                                           'P')
    else:
        return udnode.token['upostag']=='ADP'

# im, zur, zum, beim...
def is_def_preposition(udnode,language):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('APPRART',)
    else:
        return language=='fr' and udnode.token['lemma'] in ('au','aux','du')

# UD POS: CCONJ
def is_coordinating_conjunction(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('CC','KOKOM','KON','KOUS')
    else:
        return udnode.token['upostag']=='CCONJ'

# UD POS: SCONJ
def is_subordinating_conjunction(udnode):
    if(udnode.token['upostag']):
        return udnode.token['upostag']=='SCONJ'

# UD POS: PART
def is_to(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] == 'TO'
    else:
        return udnode.token['upostag']=='PART'
    
# UD POS: AUX
def is_modal(udnode,language):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('MD','VMFIN','VMINF','VMPP') and (udnode.token['form'].lower() not in ('will', 'wo') and udnode.token['lemma'] not in ('werden',))
    else:
        return (language != 'fr' and udnode.token['upostag']=='AUX') or (language=='fr' and udnode.token['upostag']=='AUX' and udnode.token['lemma'] in ('devoir','falloir','pouvoir'))

def is_auxiliary(udnode):
    return udnode.token['upostag']=='AUX' and udnode.token['lemma'] in ('be','be+not','sein','werden','être','avoir')

def is_neg_auxiliary(udnode):
    return udnode.token['upostag']=='AUX' and udnode.token['lemma'] in ('be+not',)



# doesn't, didn't
def is_neg_verb(udnode):
    return udnode.token['upostag']=='AUX' and udnode.token['lemma'] in ('do+not',)


# UD POS: NOUN
def is_noun(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'].startswith('N') or udnode.token['xpostag'] in ('TRUNC','NN',
                                                                                      # adding FW here, it can be other things
                                                                                      'FW',
                                                                                       'N_SING')
    else:
        return udnode.token['upostag']=='NOUN'

def is_noun_or_proper_noun(udnode):
    return is_noun(udnode) or is_proper_noun(udnode)
    #return False

def is_genitive(udnode):
    return udnode.token['feats'] and 'Case' in udnode.token['feats'] and udnode.token['feats']['Case']=='Gen'
    
# UD POS: ADJ
def is_adjective(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'].startswith('JJ') or udnode.token['xpostag']in('ADJA','ADJD',
                                                                                     'ADJ','ADJ_CMPR','ADJ_SUP')
    else:
        return udnode.token['upostag']=='ADJ'
    
# UD POS: ADV
def is_adverb(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'].startswith('RB') or udnode.token['xpostag']in('ADV','PWAV','PROAV',
                                                                                     # WH adverb
                                                                                     'WRB',
                                                                                     'ADV_TIME','ADV_I')
    else:
        return udnode.token['upostag']=='ADV'

def is_neg_adverb(udnode, language):
    if language == 'fr' and udnode.token['lemma'] in ('jamais'):
        return True
    else:
        return False

def is_prt_adverb(udnode,language):
    if language=='en':
        if udnode.token['lemma'] in ('off',):
            return True
        else:
            return False

def is_nuc_adverb(udnode,language):
    if language=='en':
        if udnode.token['lemma'] in ('down',):
            return True
        else:
            return False

def is_core_adverb(udnode,language):
    if language=='en':
        if udnode.token['lemma'] in ('always',):
            return True
        else:
            return False

# attaches at the root of a NP (or PP)
def is_root_adverb(udnode,language):
    if language=='en':
        if udnode.token['lemma'] in ('even',):
            return True
        else:
            return False

        
def is_pronominal_adverb(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag']in('PROAV')
    else:
        return False

# UD POS: ADV
def is_wh_adverb(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag']in ('WRB','PWAV')
    else:
        return False
    
# UD POS: VERB
def is_verb(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'].startswith('V') or udnode.token['xpostag'] in ("VVFIN","VAFIN","VVPP")
    else:
        return udnode.token['upostag']=='VERB'
    
# VerbForm = Fin
def is_finite_verb(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] in ('VBZ', 'VBP', 'VBD', 'VAFIN', 'VAIMP', 'VMFIN', 'VVFIN', 'VVIMP')
    else:
        return udnode.token['upostag']in('VERB','AUX') and udnode.token['feats'] and 'VerbForm' in udnode.token['feats'] and udnode.token['feats']['VerbForm']=='Fin'
    
# VerbForm = Part and Tense = Past
def is_past_participle(udnode):
    if(udnode.token['xpostag']):
        # it looks like we don't want the same in English and German though:
        # English -> MOD-ASP, German -> V-PART
        return udnode.token['xpostag'] in ('VBN','VVPP') 
    else:
        return udnode.token['upostag']=='VERB' and udnode.token['feats'] and 'VerbForm' in udnode.token['feats'] and udnode.token['feats']['VerbForm']=='Part' and udnode.token['feats']['Tense'] and udnode.token['feats']['Tense']=='Past'

# VerbForm = Part and Tense = Past
def is_participle(udnode):
    if(udnode.token['xpostag']):
        # it looks like we don't want the same in English and German though:
        # English -> MOD-ASP, German -> V-PART
        return udnode.token['xpostag'] in ('VBN','VVPP','VAPP') 
    else:
        return udnode.token['upostag']=='VERB' and udnode.token['feats'] and 'VerbForm' in udnode.token['feats'] and udnode.token['feats']['VerbForm']=='Part' 

def is_past(udnode):
    return 'feats' in udnode.token and udnode.token['feats'] and 'Tense' in udnode.token['feats'] and udnode.token['feats']['Tense']=='Past'

def is_present(udnode):
    return 'feats' in udnode.token and udnode.token['feats'] and 'Tense' in udnode.token['feats'] and udnode.token['feats']['Tense']=='Pres'

def is_infinitive(udnode):
    return 'feats' in udnode.token and udnode.token['feats'] and 'VerbForm' in udnode.token['feats'] and udnode.token['feats']['VerbForm']=='Inf'

def is_subjunctive(udnode):
    return 'feats' in udnode.token and udnode.token['feats'] and 'Mood' in udnode.token['feats'] and udnode.token['feats']['Mood']=='Sub'

def is_op_tns_verb(udnode):
    return 'lemma' in udnode.token and udnode.token['feats'] and udnode.token['lemma']=='haben'
    

# VerbForm = Part or Ger
def is_gerund_or_present_participle(udnode):
    if(udnode.token['xpostag']):
        return udnode.token['xpostag'] == 'VBG'
    else:
        return udnode.token['upostag']=='VERB' and udnode.token['feats'] and 'VerbForm' in udnode.token['feats'] and udnode.token['feats']['VerbForm'] in ('Part','Ger')

def precedes_subject(udnode, parent,language):
    # Is this really what we want?
    if language=='de':
        return False
    has_subject=False
    for sibling in parent.children:
        if sibling == udnode:
            continue
        if sibling.token['deprel'] == 'nsubj' and sibling.token['id'] > udnode.token['id']:
            return True
        elif sibling.token['deprel'] == 'nsubj':
            has_subject=True
    return False
    #return not has_subject

def punctuation_between(udnode, parent,language):
    # Is this really what we want?
    if language=='de':
        return False
    for sibling in parent.children+udnode.children:
        if sibling.token['deprel'] == 'punct':
            if sibling.token['id'] > udnode.token['id'] and sibling.token['id'] < parent.token['id']:
                return True
    return False

def has_expl(udnode,language):
    # Is this really what we want?
    if language=='de':
        return False
    for sibling in udnode.children:
        if sibling.token['deprel'] == 'expl':
            return True
        elif sibling.token['deprel'] == 'nsubj' and sibling.token['lemma']=='there':
            return True
    return False

def has_lemma_as_child(node,lemma):
    for child in node.children:
        if child.token['lemma']==lemma:
            return True
    return False

def is_multi_word_adverb(node):
    return node.token['lemma']=='course' and has_lemma_as_child(node,'of')\
        or node.token['lemma']=='example' and has_lemma_as_child(node,'for')\
        or node.token['lemma']=='instance' and has_lemma_as_child(node,'for')
                       

def further_cop(udnode, parent,language):
    if language=='de':
        return False
    for sibling in parent.children:
        if sibling.token['deprel'] == 'cop':
            if sibling.token['id'] < udnode.token['id']:
                return True
    return False


def precedes(udnode1,udnode2,language):
    if udnode1.token['id'] < udnode2.token['id']:
        return True
    else:
        return False


# def has_one_aux(udnode):
#     nb_aux=0
#     for child in udnode.children:
#         if child.token['deprel']=='aux':
#             nb_aux+=1
#     return nb_aux==1
    
def ud_yield(udnode):
    """Returns the yield of a UD node.

    For a conllu.models.TokenTree object udnode, this function returns a list
    of integer indices, of the tokens dominated by udnode (including udnode
    itself). The list is sorted and the indices are 0-based, so the format is
    compatible with discodop.tree.Tree.leaves().
    """
    result = []
    def collect(n):
        result.append(n.token['id'] - 1)
        for child in n.children:
            collect(child)
    collect(udnode)
    result.sort()
    return result


### PTB TREE HELPERS ##########################################################

def is_marked_as_argument(udnode):
    # consts = ptbconsts(udnode, ptbtree)
    # return any(c.label in ('PP-CLR', 'PP-PUT') for c in consts)
    return True


def is_nn(udnode):
    # consts = ptbconsts(udnode, ptbtree)
    # return any(c.label.startswith('NN') for c in consts)
    return False
    #return is_noun(udnode) or is_proper_noun(udnode)


def is_topicalized(udnode):
    # consts = ptbconsts(udnode, ptbtree)
    # return any(c.label.endswith('-TPC') for c in consts)
    return False


### RRG TREE HELPERS ##########################################################


def preterminal(udnode, pos):
    # Terminal = siblingless integer ID, 0-based position of token in sentence
    if pos=='(':
        pos='-LRB-'
    elif pos==')':
        pos='-RRB-'
    terminal = int(udnode.token['id']) - 1
    return ParentedTree(pos, [terminal])

def is_bare(tree):
    if len(tree.leaves())==1:
        return True
    else:
        return False

def peri(tree):
    not_peri_compatible={'CORE','NUC'}
    if tree.label not in not_peri_compatible:
        tree.label += '-PERI'
    return tree

def make_rel(tree):
    if len(tree.label.split('-'))==1:
        tree.label += '-REL'
    return tree 

def make_wh(tree):
    if len(tree.label.split('-'))==1:
        tree.label += '-WH'
    return tree 

def economize(tree):
    """Detaches tree if it has an empty yield.
    """
    if not tree.leaves():
        tree.detach()


def conflate(ancestor, descendant):
    """Removes unnecessary nodes.

    If ancestor and descendant have the same yield, replaces ancestor with
    descendant.
    """
    if ancestor.leaves() == descendant.leaves():
        parent = ancestor.parent
        descendant.detach()
        if parent is not None:
            ancestor.detach()
            parent.append(descendant)


def layer_priority(layer):
    if layer == 'SENTENCE':
        return 0
    if layer == 'CLAUSE':
        return 1
    if layer == 'CORE':
        return 2
    if layer == 'NUC':
        return 3
    if layer in ('XP', 'NP', 'AP', 'ADVP', 'PP', 'QP'):
        return 4
    if layer in ('CORE_X', 'CORE_N', 'CORE_A', 'CORE_ADV', 'CORE_P', 'CORE_Q'):
        return 5
    if layer in ('NUC_X', 'NUC_N', 'NUC_A', 'NUC_ADV', 'NUC_P', 'NUC_Q'):
        return 6
    if layer in ('X', 'V', 'N', 'A', 'ADV', 'P', 'QNT'):
        return 7
    return 8


def trim(tree, layer):
    """Removes unwanted RRG layers.
    """
    while layer_priority(tree.label) < layer_priority(layer) and len(tree) < 2:
        tree = tree[0]
        if tree.parent.parent is None:
            tree.detach()
        else:
            tree.parent.prune()

def one_leaf(tree):
    while tree.children:
        if not isinstance(tree.children[0],int):
            tree=tree.children[0]
        else:
            break
    return tree

def root(tree):
    while tree.parent != None:
        tree = tree.parent
    return tree


def attach_conjunct(conjunct, tree):
    """Attaches a conjunct.

    Tries to attach it at a like layer. If that fails, attaches it to CLAUSE by
    default. If that fails, attaches it to the root.
    """
    t = tree
    # some layers have only one node on the spine, for them we merge the root instead of attaching it
    one_layer={'NUC_Q',}
    if conjunct.label in one_layer:
        while t is not None:
            if t.label == conjunct.label:
                for child in conjunct.children.copy():
                    child.detach()
                    t.append(child)
                return True
            t=t.parent
    while t is not None:
        if t.parent and (t.label == conjunct.label and t.parent.label == conjunct.label):
            t.parent.append(conjunct)
            return True
        t = t.parent
    t = tree
    while t is not None:
        if t.label == 'CLAUSE' and t.parent.label == 'CLAUSE':
            t.parent.append(conjunct)
            return False
        t = t.parent
    r = root(tree)
    r.append(conjunct)

def has_above(tree,level):
    if tree.label==level:
        return False
    elif not tree.children:
        return False
    else:
        if len(tree.children)==1:
            return has_above(tree.children[0],level)
        else:
            return True

# def has_clause(tree):
#     if isinstance(tree,int):
#         return False
#     if tree.label=='CLAUSE':
#         return True
#     elif not tree.children:
#         return False
#     else:
#         for subtree in tree.children:
#             if has_clause(subtree):
#                 return True
#         return False

# returns True if a tree is rooted by CLAUSE or SENTENCE with a CLAUSE under 
def has_clause(tree):
    if isinstance(tree,int):
        return False
    elif tree.label=='CLAUSE':
        return True
    elif not tree.children:
        return False
    elif tree.label=='SENTENCE':
        for subtree in tree.children:
            if subtree.label=='CLAUSE':
                return True
        return False
    else:
        return False



        
def attach_coordinating_conjunction(coordinating_conjunction, tree, target):
    """Attaches a coordinating conjunction.

    If the attachment target is not known, attempts to attach to CLAUSE by
    default.
    """
    if target is None:
        while tree is not None:
            if tree.label == 'CLAUSE':
                tree.append(coordinating_conjunction)
                return tree
            if not tree.parent:
                #try to attach at the root
                tree.append(coordinating_conjunction)
                return tree
            tree = tree.parent
        raise Exception('failed to attach coordinating conjunction: {}'.format(coordinating_conjunction))
    else:
        if isinstance(target,ParentedTree) and len(target.children)==1 and isinstance(target.children[0],int):
            attach_coordinating_conjunction(coordinating_conjunction,tree,target.parent)
        else:
            if isinstance(target,ParentedTree):
                target.append(coordinating_conjunction)
                return target
            else:
                target=ParentedTree(target,[coordinating_conjunction])
                return target

def copy_function_tags(tree):
    for node in tree.subtrees():
        if node.source is None:
            node.source = ['--'] * 6
        if '-' in node.label and not node.label.startswith('-'):
            node.source[FUNC] = node.label.split('-', 1)[1]


### TRANSFORMATION FUNCTIONS ##################################################


# Transformation functions have diverse degrees of specialization:

# `transform` is the generic default function that transforms an UD (sub)tree
# to an RRG, choosing an RRG fragment according to the POS of the root of the
# UD tree.
#
# `transform_XYZ` functions where `XYZ` is an all-caps RRGbank POS tag produce
# an RRG tree with a specific head POS. The most important ones are
# `transform_V`, `transform_N`, `transform_A`, and `transform_ADV`, because
# they produce the layered clausal structure with SENTENCE, CLAUSE, and NUC,
# etc.
#
# `transform_xyz` functions where `xyz` is a lower-case UD dependency relation
# name expect as input UD (sub)trees with a specific dependency relation at the
# root, and produce corresponding RRG trees.
#
# There are also some `transform_XYZ_xyz` functions that are specialized to
# specific combinations of head parts of speech and dependency relation.



def transform_punctuation(udnode, language, layer='X'):
    # make fragment
    postag=udnode.token['xpostag']
    if not postag or postag=='DELM':
        postag=udnode.token['upostag']
        # do better later
        postag='.'
    if postag[0]=='$':
        postag=postag[1:]
    punctuation = preterminal(udnode, postag)
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return punctuation

def transform_punctuation_root(udnode, language, layer='X'):
    # this is obviously a parsing mistake
    # just reaffect the root to one of the children
    new_root=None
    for child in udnode.children :
        new_root=child
        if new_root.token['deprel']!='punct':
            break
    # if all children are also punct, try further descendents (Todo: clean and complete recursion)
    if new_root.token['deprel'] == 'punct':
        for child in udnode.children:
            for grandchild in child.children:
                new_root=grandchild
                if new_root.token['deprel']!='punct':
                    child.children.remove(new_root)
                    udnode.children.append(new_root)
                    break
    if new_root.token['deprel'] == 'punct':
        for child in udnode.children:
            for grandchild in child.children:
                for grandgrandchild in grandchild.children:
                    new_root=grandgrandchild
                    if new_root.token['deprel']!='punct':
                        grandchild.children.remove(new_root)
                        udnode.children.append(new_root)
                        break

        
    
    
    udnode.children.remove(new_root)
    new_root.token['deprel']='root'
    new_root.token['head']=0
    for child in udnode.children:
        child.token['head']=new_root.token['id']
        new_root.children.append(child)

    udnode.children=[]
    udnode.token['deprel']='punct'
    udnode.token['head']=new_root.token['id']
    new_root.children.append(udnode)
    return transform(new_root,language)


def transform_possessive_ending(udnode, language, layer='X'):
    # make fragment
    pos = preterminal(udnode, 'POS')
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return pos


def transform_NEG_OP(udnode, language, layer='X'):
    # make fragment
    def_op = preterminal(udnode, 'OP-NEG')
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return def_op


def transform_PDT(udnode, language, layer='X'):
    # make fragment
    def_op = preterminal(udnode, 'PDT')
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return def_op


def transform_DEF_OP(udnode, language, layer='X'):
    # make fragment
    def_op = preterminal(udnode, 'OP-DEF')
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return def_op


def transform_CLM(udnode, language, layer='X'):
    # make fragment
    clm = preterminal(udnode, 'CLM')
    # recur
    punctuation=[]
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return clm


def transform_P(udnode, language, layer='X'):
    # make fragment
    if language=='fr' and udnode.token['lemma']=='Oe':
        # for O' in O'Brien
        udnode.token['upostag']='PROPN'
        udnode.token['deprel']='compound'
        return transform_N(udnode,language,layer)
    pp = ParentedTree('PP', [])
    core_p = ParentedTree('CORE_P', [])
    nuc_p = ParentedTree('NUC_P', [])
    if is_def_preposition(udnode,language):
        p = preterminal(udnode, 'P-DEF')
    else:
        p = preterminal(udnode, 'P')        
    nuc_p.append(p)
    core_p.append(nuc_p)
    pp.append(core_p)
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    trim(pp, layer)
    return root(p)

def transform_P_root(udnode, language, layer='X'):
    # this happens in sentences 1278, 1943(en), where P is an ADV in the gold data
    sentence = ParentedTree('SENTENCE', [])    
    sentence.append(transform_ADV(udnode,language))
    return root(sentence)

    # # this is certainly a parsing mistake (4650)
    # # just reaffect the root to one of the children
    # new_root=udnode.children[0]
    # # should be some more clever choice of the new root
    # new_root.token['deprel']='root'
    # new_root.token['head']=0
    # udnode.children.remove(new_root)

    # for child in udnode.children:
    #     child.token['head']=new_root.token['id']
    #     new_root.children.append(child)

    # udnode.children=[]
    # # maybe something more universal than case?
    # udnode.token['deprel']='case'
    # udnode.token['head']=new_root.token['id']
    # new_root.children.append(udnode)
    # return transform(new_root,ptbtree,language)


def transform_PRT(udnode, language, layer='X'):
    # make fragment
    pp = ParentedTree('PP', [])
    core_p = ParentedTree('CORE_P', [])
    nuc_p = ParentedTree('NUC_P', [])
    p = preterminal(udnode, 'PRT')
    nuc_p.append(p)
    core_p.append(nuc_p)
    pp.append(core_p)
    punctuation=[]
    # recur
    for child in udnode.children:
        if child.token['deprel'] in ('conj', 'discourse', 'parataxis'):
            if is_nn(child):
                if is_proper_noun(child):
                    conjunct = preterminal(child, 'N-PROP')
                else:
                    conjunct = preterminal(child, 'N')
                nuc_p.append(conjunct)
                current_conjunct = nuc_p
            else:
                conjunct = transform_N(child, language)
                attach_conjunct(conjunct, p)
                current_conjunct = conjunct
        elif child.token['deprel'] == 'cc':
            coordinating_conjunction = transform_CLM(child, language)
            attach_coordinating_conjunction(coordinating_conjunction, p, nuc_p)
        elif child.token['deprel'] in ('nsubj',):
                core_p.append(transform_N(child, language))
        elif child.token['deprel'] in ('aux','cop'):
                core_p.append(transform_AUX(child, language))
        elif child.token['deprel'] in ('nmod',):
                core_p.append(transform_N(child, language))
        elif child.token['deprel'] in ('advmod',):
                core_p.append(transform_ADV(child, language))
        elif child.token['deprel'] in ('advcl',):
                core_p.append(transform(child, language))
        elif child.token['deprel'] in ('ccomp',):
                core_p.append(transform(child, language))
        elif child.token['deprel'] == 'punct':
            punctuation.append(transform(child, language))
        else:
            raise NotHandled(child)
    trim(pp, layer)
    tree=root(p)
    if punctuation:
        linkage.add_punctuation(tree, punctuation)
    tree=root(p)
    return tree


def transform_ADV(udnode, language, layer='XP'):
    # make fragment
    if layer_priority(layer)==7:
        for child in udnode.children:
            raise NotHandled(child)

        return preterminal(udnode,'ADV')
    
    supercore = ParentedTree('CORE', [])
    sentence1 = ParentedTree('SENTENCE', [])
    sentence2 = ParentedTree('SENTENCE', [])
    clause1 = ParentedTree('CLAUSE', [])
    clause2 = ParentedTree('CLAUSE', [])
    prcs = ParentedTree('PrCS', [])
    core1 = ParentedTree('CORE', [])
    core2 = ParentedTree('CORE', [])
    nuc = ParentedTree('NUC', [])
    pp1 = ParentedTree('PP', [])
    pp2 = ParentedTree('PP', [])
    core_p = ParentedTree('CORE_P', [])
    nuc_p = ParentedTree('NUC_P', [])
    advp1 = ParentedTree('ADVP', [])
    advp2 = ParentedTree('ADVP', [])
    core_adv = ParentedTree('CORE_ADV', [])
    nuc_adv = ParentedTree('NUC_ADV', [])
    if is_wh_adverb(udnode):
        adv = preterminal(udnode, 'PRO-WH')
        advp2.label += '-WH' # todo refactor this?
    elif is_pronominal_adverb(udnode):
        adv=preterminal(udnode,'PRO')
    # for "of course", treated as an ADVP-PERI
    elif is_multi_word_adverb(udnode):
        adv = preterminal(udnode,'N')
    elif is_neg_adverb(udnode,language):
        adv = preterminal(udnode, 'ADV-NEG')
    else:
        adv = preterminal(udnode, 'ADV')
        
        
    nuc_adv.append(adv)
    core_adv.append(nuc_adv)
    advp2.append(core_adv)
    advp1.append(advp2)
    core_p.append(advp1)
    core_p.append(nuc_p)
    pp2.append(core_p)
    pp1.append(pp2)
    nuc.append(pp1)
    core2.append(nuc)
    core1.append(core2)
    clause2.append(core1)
    clause2.append(prcs)
    clause1.append(clause2)
    sentence2.append(clause1)
    sentence1.append(sentence2)
    supercore.append(sentence1)
    punctuation = []
    # recur
    current_conjunct = None
    again=True
    more_children=[]
    while again:
        again=False
        if more_children:
            udnode.children=more_children
        more_children=[]
        for child in reversed(udnode.children):
            if child.token['deprel'].startswith('advmod') or child.token['deprel'] in ('fixed',):
                if is_neg_particle(child,language):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    core_adv.append(transform_NEG_OP(child, language))
                elif is_noun(child):
                    core_adv.append(transform_N(child, language))
                else:
                    #nuc.append(peri(transform_ADV(child, ptbtree,language)))
                    core_adv.append(peri(transform_ADV(child, language)))
              
            elif child.token['deprel'] in ('aux',):
                if is_modal(child,language):
                    core2.append(transform_MOD_OP(child, language))
                else:
                    clause2.append(transform_TNS_OP(child, language))
            elif child.token['deprel'] in ('aux:q',):
                if is_modal(child,language):
                    core2.append(transform_MOD_OP(child, language))
                else:
                    clause2.append(transform_TNS_OP(child, language))
            elif child.token['deprel'] == 'case':
                if is_preposition(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                if is_possessive_ending(child):
                    advp2.append(transform_possessive_ending(child, language))
                # for "of course", treated as an ADVP-PERI
                #elif udnode.token['lemma']=='course' and child.token['lemma']=='of':
                elif is_multi_word_adverb(udnode) and child.token['lemma'] in ('of','for'):
                    nuc_adv.append(transform(child, language))                    
                else:
                    nuc_p.append(transform(child, language))
            elif child.token['deprel'] == 'cc':
                if child.children:
                    more_children+=child.children
                    child.children=[]
                coordinating_conjunction = transform_CLM(child, language)
                attach_coordinating_conjunction(coordinating_conjunction, adv, current_conjunct)
            elif child.token['deprel'] == 'conj':
                if is_punctuation(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                conjunct = transform(child, language)
                attach_conjunct(conjunct, adv)
                current_conjunct = conjunct
            elif child.token['deprel'] in ('cop', 'auxpass','aux:pass'):
                nuc.append(transform_AUX(child, language))
            elif child.token['deprel'] == 'dep':
                core_adv.append(peri(transform(child, language)))
            elif child.token['deprel'] in ('det','det:poss'):
                #core_adv.append(peri(transform_determiner(child, ptbtree,language)))
                # here the ADV is treated as a noun, relabel everything:
                core_adv.label='CORE_N'
                advp2.label='NP'
                advp1.label='NP'
                if child.children:
                    more_children+=child.children
                    child.children=[]
                advp2.append(transform_determiner(child, language))
                
            elif child.token['deprel'] =='mwe':
                nuc_adv.append(transform_ADV(child, language, layer='X'))
            elif child.token['deprel'] == 'neg':
                core_adv.append(transform_NEG_OP(child, language))
            elif child.token['deprel'].startswith('nmod') or child.token['deprel'] in ('obl','obl:tmod','goeswith'):
                if is_preposition(child):
                    nominal_modifier = transform_P(child, language, layer='XP')
                elif is_cardinal(child):
                    nominal_modifier = transform_QNT_referential(child, language)
                else:  
                    nominal_modifier = transform_N(child, language)
                if not is_marked_as_argument(child):
                    core_adv.append(nominal_modifier)
                else:
                    advp2.append(peri(nominal_modifier))
            elif child.token['deprel'] in ('obl:npmod',):
                if is_preposition(child):
                    nominal_modifier = transform_P(child, language, layer='XP')
                elif is_cardinal(child):
                    nominal_modifier = transform_QNT_referential(child, language)
                else:  
                    nominal_modifier = transform_N(child, language)
                core_adv.append(nominal_modifier)
          
            elif child.token['deprel'] in ('nsubj', 'nsubjpass','nsubj:pass', 'expl', 'dobj', 'iobj','obj'):
                core2.append(transform(child, language))
            elif child.token['deprel'] == 'punct':
                if child.children:
                    more_children+=child.children
                    child.children=[]
                punctuation.append(transform(child, language))
                #layer='SENTENCE'
            elif child.token['deprel'] == 'mark':
                if is_particle(child):
                    # for "zu groß" for instance
                    nuc_adv.append(peri(transform_ADV(child,language)))
                else:
                    if child.token['lemma']=='to' or child.token['xpostag']=='KOUI':
                        core2.append(transform_CLM(child, language))
                    else:
                        if child.children:
                            more_children+=child.children
                            child.children=[]
                        clause2.append(transform_CLM(child, language))
            elif child.token['deprel'] in ('conj', 'discourse', 'parataxis'):
                if is_particle(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                if is_adverb(child):
                    conjunct = transform(child,language,layer='ADVP')
                    attach_conjunct(conjunct,advp2)
                    current_conjunct=advp2
                else:
                    conjunct = transform(child, language)
                    attach_conjunct(conjunct, adv)
                    current_conjunct = conjunct
            elif child.token['deprel'] in ('advcl','acl','acl:relcl'):
                # probably parsing errors (children are verbs)
                advp2.append(transform(child,language))
            elif child.token['deprel'] in ('csubj',):
                if language=='ru' and is_verb(child):
                    #nuc.append(transform_V(child,ptbtree,language,layer='NUC'))
                    core2.append(transform_V(child,language))
                else:
                    advp2.append(transform(child,language))                    
            elif child.token['deprel'] in ('appos'):
                if is_cardinal(child):
                    core_adv.append(peri(transform_N(child,language)))
                else:
                    core_adv.append(peri(transform(child, language)))
            elif child.token['deprel'].startswith('amod'):
                adjectival_modifier = transform(child, language, layer='X')
                nuc_adv.append(adjectival_modifier)
            elif child.token['deprel'].startswith('ccomp'):
                clausal_complement = transform(child, language, layer='SENTENCE')
                linkage.clause_sub(sentence1, sentence2, clause1, clause2, core1,
                                   core2, nuc_adv, nuc_adv, clausal_complement)
            elif child.token['deprel'] in ('compound','compound:prt'):
                if child.children:
                    more_children=child.children
                    child.children=[]
                compound = transform(child, language,layer='NUC')
                clause2.append(compound)

            else:
                raise NotHandled(child)
        if more_children:
            again=True           
    economize(prcs)
    conflate(supercore, sentence1)
    conflate(sentence1, sentence2)
    conflate(clause1, clause2)
    conflate(core1, core2)
    conflate(pp1, pp2)
    conflate(pp2, advp1)
    conflate(advp1, advp2)
    if udnode.token['lemma']=='yes':
        # just an ADV under an ADVP
        conflate(core_adv, adv)
    if is_wh_adverb(udnode) or is_pronominal_adverb(udnode):
        conflate(core_adv, adv)
    trim(sentence2, layer)
    tree = root(adv)
    linkage.add_punctuation(tree, punctuation)
    tree = root(adv)
    return tree


def transform_A(udnode, language, layer='XP'):
    # make fragment
    supercore = ParentedTree('CORE', [])
    sentence1 = ParentedTree('SENTENCE', [])
    sentence2 = ParentedTree('SENTENCE', [])
    clause1 = ParentedTree('CLAUSE', [])
    clause2 = ParentedTree('CLAUSE', [])
    prcs = ParentedTree('PrCS', [])
    core1 = ParentedTree('CORE', [])
    core2 = ParentedTree('CORE', [])
    nuc1 = ParentedTree('NUC', [])
    nuc2 = ParentedTree('NUC', [])
    pp1 = ParentedTree('PP', [])
    pp2 = ParentedTree('PP', [])
    core_p = ParentedTree('CORE_P', [])
    nuc_p = ParentedTree('NUC_P', [])
    ap1 = ParentedTree('AP', [])
    ap2 = ParentedTree('AP', [])
    core_a = ParentedTree('CORE_A', [])
    nuc_a = ParentedTree('NUC_A', [])
    if is_verb(udnode) and is_gerund_or_present_participle(udnode):
        a = preterminal(udnode, 'V-GER')
    elif is_verb(udnode) and  is_past_participle(udnode):
        a = preterminal(udnode, 'V-PART')
    else:
        a = preterminal(udnode, 'A')
    nuc_a.append(a)
    core_a.append(nuc_a)
    ap2.append(core_a)
    ap1.append(ap2)
    core_p.append(nuc_p)
    core_p.append(ap1)
    pp2.append(core_p)
    pp1.append(pp2)
    nuc2.append(pp1)
    nuc1.append(nuc2)
    core2.append(nuc1)
    core1.append(core2)
    clause2.append(core1)
    clause2.append(prcs)
    clause1.append(clause2)
    sentence2.append(clause1)
    sentence1.append(sentence2)
    supercore.append(sentence1)
    punctuation = []
    # recur
    current_conjunct = None
    again=True
    more_children=[]
    while again:
        again=False
        if more_children:
            udnode.children=more_children
        more_children=[]
        for child in reversed(udnode.children):
            if child.token['deprel'] == 'advcl':
                adverbial_clause = transform(child, language, layer='CORE')
                if not is_marked_as_argument(child):
                    adverbial_clause = peri(adverbial_clause)
                core2.append(adverbial_clause)
            elif child.token['deprel'].startswith('advmod'):
                if is_neg_particle(child,language):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    core2.append(transform_NEG_OP(child,language))
                elif child.token['xpostag']=='ADJD':
                    core_a.append(peri(transform_ADV(child,language)))
                else:
                    # this is at nuc_a sometimes ("sehr interessant" for instance)
                    # but this seems to create problems
                    if is_core_adverb(child,language):
                        core2.append(peri(transform_ADV(child,language)))
                    else:
                        nuc_a.append(peri(transform_ADV(child,language)))
                    #core_a.append(peri(transform_ADV(child, ptbtree,language)))
            elif child.token['deprel'].startswith('amod') or child.token['deprel'] in ('acl','acl:relcl'):
                if is_adverb(child) and child.children:
                    more_children+=child.children
                    child.children=[]
                adjectival_modifier = transform(child, language, layer='X')
                nuc_a.append(adjectival_modifier)
            elif child.token['deprel'] in ('aux'):
                if is_modal(child,language) or is_subjunctive(child):
                    core2.append(transform_MOD_OP(child, language))
                else:
                    clause2.append(transform_TNS_OP(child,language))
            elif child.token['deprel'] == 'case':
                if is_possessive_ending(child):
                    nuc_p.append(transform_possessive_ending(child,language))
                else:
                    nuc_p.append(transform(child,language))
            elif child.token['deprel'] in ('cc','cc:preconj'):
                if child.children:
                    more_children+=child.children
                    child.children=[]
                coordinating_conjunction = transform_CLM(child,language)
                #attach_coordinating_conjunction(coordinating_conjunction, a, current_conjunct)
                attach_coordinating_conjunction(coordinating_conjunction, a, ap2)
            elif child.token['deprel'].startswith('ccomp'):
                clausal_complement = transform(child,language, layer='SENTENCE')
                linkage.clause_sub(sentence1, sentence2, clause1, clause2, core1,
                                   core2, nuc1, nuc2, clausal_complement)
            elif child.token['deprel'] in ('conj', 'discourse', 'parataxis'):
                if is_adjective(child):
                    conjunct = transform(child,language,layer='AP')
                    attach_conjunct(conjunct,ap2)
                    current_conjunct=ap2
                else:
                    if is_preposition(child) or is_punctuation(child):
                        if child.children:
                            more_children+=child.children
                            child.children=[]
                    conjunct = transform(child,language)
                    attach_conjunct(conjunct, a)
                    current_conjunct = conjunct
            elif child.token['deprel'] in ('cop', 'auxpass','aux:pass'):
                nuc2.append(transform_AUX(child,language))
            elif child.token['deprel'] == 'dep':
                core_a.append(transform(child, language))
            elif child.token['deprel'] == 'csubj':
                core2.append(transform(child,language, layer='CORE'))
            elif child.token['deprel'] == 'mark':
                if is_particle(child):
                    # for "zu groß" for instance
                    nuc_a.append(peri(transform_ADV(child,language)))
                else:
                    # at least for "that":
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    if child.token['lemma']=='to' or child.token['xpostag']=='KOUI':
                        core2.append(transform_CLM(child,language))
                    else:
                        clause2.append(transform_CLM(child,language))
                        
            elif child.token['deprel'] == 'neg':
                core2.append(transform_NEG_OP(child,language))
            elif child.token['deprel'].startswith('nmod') or child.token['deprel'] in ('obl','obl:npmod','obl:tmod','obl:agent','goeswith'):
                if is_adverb(child) or is_multi_word_adverb(child):
                    nominal_modifier = peri(transform_ADV(child,language, layer='XP'))                
                elif is_preposition(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    nominal_modifier = transform_P(child,language, layer='XP')
                elif is_cardinal(child):
                    nominal_modifier = transform_QNT_referential(child,language)
                else:
                    nominal_modifier = transform_N(child,language)
                if is_marked_as_argument(child) or is_preposition(child):
                    core_a.append(nominal_modifier)
                else:
                    core2.append(peri(nominal_modifier))
            elif child.token['deprel'] == 'obl:arg':
                # L4: replica bajo cabeza ADJETIVAL el dispatch que L3 anadio
                # a transform_V para obl:arg. MISC manda; sin MISC, fallback
                # es: clitico atono -> AGX, si no -> argumento del CORE_A.
                # Otras lenguas sin MISC: NotHandled (este deprel nunca
                # estaba en el dispatch de transform_A).
                rrg_misc = child.token.get('misc') or {}
                rrg_role = rrg_misc.get('RRGRole')
                if rrg_role == 'AGX' or (rrg_role is None and language == 'es' and is_clitic_pronoun(child, language) and not _es_conllu_analizado(udnode)):
                    nuc_a.append(preterminal(child, 'AGX'))
                elif rrg_role in ('CoreArg', 'Periphery') or (rrg_role is None and language == 'es'):
                    if is_preposition(child):
                        if child.children:
                            more_children += child.children
                            child.children = []
                        nominal_modifier = transform_P(child, language, layer='XP')
                    else:
                        nominal_modifier = transform_N(child, language)
                    if rrg_role == 'Periphery':
                        # Etapa PERIFERIA (Julian 2026-07-13): anclaje
                        # scope-driven vía RRGStratum (nucleo/centro/
                        # clausula) -- reemplaza el viejo "temporal siempre
                        # CLAUSE" de L3.
                        nominal_modifier = peri(nominal_modifier)
                        estrato = rrg_misc.get('RRGStratum', 'centro')
                        if estrato == 'clausula':
                            clause2.append(nominal_modifier)
                        elif estrato == 'nucleo':
                            nuc_a.append(nominal_modifier)
                        else:
                            core_a.append(nominal_modifier)
                    else:
                        core_a.append(nominal_modifier)
                else:
                    raise NotHandled(child)
            elif child.token['deprel'] in ('nsubj', 'nsubjpass','nsubj:pass', 'expl', 'dobj', 'iobj','obj'):
                if is_wh_pronoun(child) or is_wh_determiner(child) or is_rel_pronoun(child) or is_rel_determiner(child):
                    prcs.append(transform(child,language))
                else:
                    core2.append(transform(child,language))
            elif child.token['deprel'] == 'punct':
                if child.children:
                    more_children+=child.children
                    child.children=[]
                punctuation.append(transform(child,language))
                #layer='SENTENCE'
            elif child.token['deprel'] == 'xcomp':
                # this is at least for "un/able to" and "supposed to"
                if is_verb(child) and is_infinitive(child):
                    open_clausal_complement = transform(child,language, layer='CORE')
                    # linkage.core_sub(sentence1, sentence2, clause1, clause2, core1,
                    #                  core2, nuc1, nuc2, open_clausal_complement)
                    linkage.core_cosub(sentence1, sentence2, clause1, clause2, core1,
                                       core2, nuc1, nuc2, open_clausal_complement)

                else:
                    open_clausal_complement = transform(child, language, layer='SENTENCE')
                    # linkage.core_sub(sentence1, sentence2, clause1, clause2, core1,
                    #                  core2, nuc1, nuc2, open_clausal_complement)
                    linkage.clause_sub(sentence1, sentence2, clause1, clause2, core1,
                                       core2, nuc1, nuc2, open_clausal_complement)
            elif child.token['deprel'] in ('det','det:poss', 'det:predet', 'nmod:poss'):
                ap2.append(transform_determiner(child, language))
            elif child.token['deprel'] in ('appos'):
                if is_cardinal(child):
                    core_a.append(peri(transform_N(child, language)))
                else:
                    core_a.append(peri(transform(child, language)))
            elif child.token['deprel'] in ('compound','compound:prt'):
                if child.children:
                    more_children=child.children
                    child.children=[]
                compound = transform(child, language,layer='NUC')
                clause2.append(compound)
            elif child.token['deprel'] in ('compound:redup'):
                if child.children:
                    more_children=child.children
                    child.children=[]
                compound = transform_A(child, language,layer='NUC')
                clause2.append(compound)
            elif child.token['deprel'] in ('compound:lvc'):
                if child.children:
                    more_children=child.children
                    child.children=[]
                compound = transform(child, language,layer='NUC')
                clause2.append(compound)
            elif child.token['deprel'] in ('fixed',):
                if is_subordinating_conjunction(child):
                    core2.append(transform_CLM(child, language))                
                else:
                    core2.append(transform(child, language))
            elif child.token['deprel'] in ('vocative',):
                core2.append(transform(child, language))
            elif child.token['deprel'] in ('nummod','nummod:gov'):
                core_a.append(transform(child, language, layer='XP'))
            else:
                raise NotHandled(child)
        if more_children:
            again=True           
    economize(prcs)
    conflate(supercore, sentence1)
    conflate(sentence1, sentence2)
    conflate(clause1, clause2)
    conflate(core1, core2)
    conflate(nuc1, nuc2)
    conflate(pp1, pp2)
    conflate(pp2, ap1)
    conflate(ap1, ap2)
    trim(sentence2, layer)
    tree = root(a)
    linkage.add_punctuation(tree, punctuation)
    tree=root(a)
    return tree


def transform_N_unspecified_dependency(udnode, language, layer='X'):
    # make fragment
    n = preterminal(udnode, 'N')
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return n


def transform_QNT(udnode,language, layer='XP'):
    # make fragment
    qp = ParentedTree('QP', [])
    core_q = ParentedTree('CORE_Q', [])
    nuc_q = ParentedTree('NUC_Q', [])
    qnt = preterminal(udnode, 'QNT')
    nuc_q.append(qnt)
    core_q.append(nuc_q)
    qp.append(core_q)
    punctuation=[]
    more_children=[]
    # recur
    for child in udnode.children:
        if child.token['deprel'] in ('compound'):
            compound = transform(child, language, layer='X')
            nuc_q.append(compound)
        elif child.token['deprel'] in ('conj','nummod:gov','appos'):
            if child.children:
                more_children+=child.children
                child.children=[]
            conjunct = transform(child, language, layer='X')
            conjunct.detach()
            attach_conjunct(conjunct,nuc_q)
        elif child.token['deprel'] in ('nummod',):
            conjunct = transform(child, language, layer='XP')
            attach_conjunct(conjunct,qp)
        elif child.token['deprel'] in ('flat',):
            nuc_q.append(transform(child, language, layer='X'))
        elif child.token['deprel'] in ('expl',):
            # existential there
            expl = transform(child, language, layer='X')
            core_q.append(expl)
        elif child.token['deprel'] in ('parataxis','advcl'):
            conjunct = transform(child, language, layer='X')
            attach_conjunct(conjunct,qp)
        elif child.token['deprel'].startswith('advmod'):
            core_q.append(peri(transform_ADV(child,language)))
        elif child.token['deprel'].startswith('amod'):
            nuc_q.append(peri(transform_A(child,language)))
        elif child.token['deprel'].startswith('nmod'):
            nuc_q.append(peri(transform_N(child,language)))
        elif child.token['deprel'].startswith('obl'):
            nuc_q.append(peri(transform_N(child,language)))
        elif child.token['deprel'] == 'cc':
            coordinating_conjunction = transform_CLM(child,language)
            if is_coordinating_conjunction(child):
                current_conjunct=nuc_q
            attach_coordinating_conjunction(coordinating_conjunction, qp, current_conjunct)
        elif child.token['deprel'] in ('nsubj',):
                core_q.append(transform_N(child,language))
        elif child.token['deprel'] in ('cop', 'auxpass','aux:pass','aux'):
                nuc_q.append(transform_AUX(child,language))
        elif child.token['deprel'] in ('punct',):
                punctuation.append(transform_punctuation(child,language))
        elif child.token['deprel'] in ('mark',):
                core_q.append(transform(child,language))
        # here should be the dep: POS?
        elif is_possessive_ending(child):
            qp.append(transform_possessive_ending(child,language))
        elif child.token['deprel'] in ('det',):
            qp.append(transform(child,language))
        elif child.token['deprel'] in ('obj',):
            qp.append(transform(child,language))
        elif child.token['deprel'] in ('acl','acl:relcl'):
            core_q.append(peri(transform(child,language)))
        elif child.token['deprel'] in ('cc','cc:preconj'):
            coordinating_conjunction = transform_CLM(child,language)
            attach_coordinating_conjunction(coordinating_conjunction, qnt, qp)
        elif child.token['deprel'] == 'case':
            if is_preposition(child):
                if child.children:
                            more_children+=child.children
                            child.children=[]
            nuc_q.append(transform(child,language, layer='X'))
        elif child.token['deprel'] in ('fixed',):
            qp.append(transform(child, language))
        else:
            raise NotHandled(child)
    for child in more_children:
        if child.token['deprel'] in ('cc','cc:preconj'):
            coordinating_conjunction = transform_CLM(child, language)
            attach_coordinating_conjunction(coordinating_conjunction, qnt, qp)
        elif child.token['deprel'] in ('obj',):
            qp.append(transform(child, language))
        elif child.token['deprel'] in ('nummod',):
            conjunct = transform(child, language, layer='XP')
            attach_conjunct(conjunct,qp)
        elif child.token['deprel'] in ('punct',):
                punctuation.append(transform_punctuation(child, language))
        elif child.token['deprel'] in ('fixed',):
            qp.append(transform(child, language))
        elif child.token['deprel'] in ('flat',):
            nuc_q.append(transform(child, language, layer='X'))
        else:
            raise NotHandled(child)
    
    # return
    trim(qp, layer)
    tree = root(qnt)
    linkage.add_punctuation(tree, punctuation)
    tree = root(qnt)
    return tree


def transform_QNT_referential(udnode, language, layer='XP'):
    # make fragment
    sentence1 = ParentedTree('SENTENCE', [])
    sentence2 = ParentedTree('SENTENCE', [])
    prdp = ParentedTree('PrDP', [])
    clause1 = ParentedTree('CLAUSE', [])
    clause2 = ParentedTree('CLAUSE', [])
    prcs = ParentedTree('PrCS', [])
    core1 = ParentedTree('CORE', [])
    core2 = ParentedTree('CORE', [])
    nuc1 = ParentedTree('NUC', [])
    nuc2 = ParentedTree('NUC', [])
    pp = ParentedTree('PP', [])
    core_p = ParentedTree('CORE_P', [])
    nuc_p = ParentedTree('NUC_P', [])
    np1 = ParentedTree('NP', [])
    np = ParentedTree('NP', [])
    core_n = ParentedTree('CORE_N', [])
    nuc_q = ParentedTree('NUC_Q', [])
    qnt = preterminal(udnode, 'QNT')
    nuc_q.append(qnt)
    core_n.append(nuc_q)
    np.append(core_n)
    np1.append(np)
    core_p.append(np1)
    core_p.append(nuc_p)
    pp.append(core_p)
    nuc2.append(pp)
    nuc1.append(nuc2)
    core2.append(nuc1)
    core1.append(core2)
    clause2.append(core1)
    clause2.append(prcs)
    clause1.append(clause2)
    sentence2.append(clause1)
    sentence2.append(prdp)
    sentence1.append(sentence2)
    punctuation = []
    more_children = []
    # recur
    for child in udnode.children:
        if child.token['deprel'].startswith('advmod'):
            adverbial_modifier = peri(transform_ADV(child, language))
            if precedes_subject(child, udnode,language):
                clause2.append(adverbial_modifier)
            else:
                nuc_q.append(adverbial_modifier)
        elif child.token['deprel'].startswith('amod') or child.token['deprel'] in ('acl','acl:relcl'):
            core_n.append(peri(transform(child, language)))
        elif child.token['deprel'] == 'case':
            nuc_p.append(transform(child, language, layer='X'))
        elif child.token['deprel'] in ('cop', 'auxpass','aux:pass','aux'):
            nuc2.append(transform_AUX(child, language))
        elif child.token['deprel'] in ('dep','flat'):
            # in this case, better do this than fail
            if child.children:
                unspecified_dependency = transform_N(child, language, layer='X')
            else:
                unspecified_dependency = transform_N_unspecified_dependency(child, language, layer='X')
            core_n.append(unspecified_dependency)
        elif child.token['deprel'] in ('det','det:poss', 'nmod:poss'):
            if child.children:
                more_children+=child.children
                child.children=[]
            np.append(transform_determiner(child, language))
        elif child.token['deprel'].startswith('nmod') or child.token['deprel']=='obl':
            nominal_modifier = transform_N(child,language)
            if is_marked_as_argument(child):
                core_n.append(nominal_modifier)
            else:
                np.append(peri(nominal_modifier))
        elif child.token['deprel'] in ('nsubj', 'nsubjpass','nsubj:pass', 'expl', 'dobj', 'iobj','obj'):
            if is_wh_pronoun(child) or is_wh_determiner(child) or is_rel_pronoun(child) or is_rel_determiner(child):
                prcs.append(transform(child, language))
            else:
                core2.append(transform(child, language))
        elif child.token['deprel'] in ('csubj',):
            conjunct = transform(child, language)
            attach_conjunct(conjunct,np)      
        elif child.token['deprel'] == 'punct':
            if child.children:
                more_children+=child.children
                child.children=[]
            punctuation.append(transform(child, language))
            #layer='SENTENCE'
        elif child.token['deprel'] == 'mark':
            core2.append(transform_CLM(child, language))
        elif child.token['deprel'] in ('conj','advcl','discourse','parataxis'):
            # if is_cardinal(child):
            #     if child.children:
            #         more_children+=child.children
            #         child.children=[]
            if is_adverb(child):
                conjunct = transform(child, language, layer='ADVP')
            else:
                conjunct = transform(child, language, layer='X')
            attach_conjunct(conjunct,nuc_q)
        elif child.token['deprel'] in ('appos'):
            if is_cardinal(child):
                conjunct = transform_QNT_referential(child, language, layer='XP')
            else:
                conjunct = transform_QNT(child, language, layer='XP')
            attach_conjunct(conjunct,np)
            #np.append(conjunct)
        elif child.token['deprel'] in ('nummod'):
            if is_cardinal(child):
                conjunct = transform_QNT_referential(child, language, layer='XP')
            else:
                conjunct = transform_QNT(child, language, layer='XP')
            attach_conjunct(conjunct,np)
            #np.append(conjunct)

        elif child.token['deprel'] in ('compound',):
            conjunct = transform(child, language, layer='X')
            attach_conjunct(conjunct,nuc_q)      
        elif child.token['deprel'] in ('ccomp',):
            conjunct = transform(child, language)
            attach_conjunct(conjunct,np)      
        elif child.token['deprel'] in ('cc','cc:preconj'):
            coordinating_conjunction = transform_CLM(child, language)
            attach_coordinating_conjunction(coordinating_conjunction, qnt, pp)
        else:
            raise NotHandled(child)
    for child in more_children:
        if child.token['deprel'] == 'punct':
            punctuation.append(transform(child, language))
            #layer='SENTENCE'        
        elif child.token['deprel'] in ('det','det:poss', 'nmod:poss'):
            np.append(transform_determiner(child, language))
        elif child.token['deprel'] in ('nummod'):
            if is_cardinal(child):
                conjunct = transform_QNT_referential(child, language, layer='XP')
            else:
                conjunct = transform_QNT(child, language, layer='XP')
            attach_conjunct(conjunct,np)
            #np.append(conjunct)
        else:
            raise NotHandled(child)
    # return
    economize(prdp)
    economize(prcs)
    conflate(sentence1, sentence2)
    conflate(clause1, clause2)
    conflate(core1, core2)
    conflate(core2, pp)
    conflate(nuc1, nuc2)
    conflate(pp, np1)
    conflate(np1,np)
    trim(sentence2, layer)
    tree = root(qnt)
    linkage.add_punctuation(tree, punctuation)
    return tree


def transform_N_determiner(udnode, language):
    if language=='fa':
        npip = ParentedTree('NPFP', [])
    else:
        npip = ParentedTree('NPIP', [])
    npip.append(transform_N(udnode, language))
    return npip


def transform_N(udnode, language, layer='XP'):
    # if is_personal_pronoun(udnode) and udnode.token['lemma']=='one':
    #     return transform_QNT_referential(udnode,language,layer)
    # make fragment

    # fix some tagging mistakes
    if language=='fr' and udnode.token['lemma']=='Winston' and udnode.token['upostag']=='PRON':
        udnode.token['upostag']='PROPN'
    
    supercore = ParentedTree('CORE', [])
    sentence1 = ParentedTree('SENTENCE', [])
    sentence2 = ParentedTree('SENTENCE', [])
    prdp = ParentedTree('PrDP', [])
    clause1 = ParentedTree('CLAUSE', [])
    clause2 = ParentedTree('CLAUSE', [])
    prcs = ParentedTree('PrCS', [])
    core1 = ParentedTree('CORE', [])
    core2 = ParentedTree('CORE', [])
    nuc1 = ParentedTree('NUC', [])
    nuc2 = ParentedTree('NUC', [])
    pp1 = ParentedTree('PP', [])
    pp2 = ParentedTree('PP', [])
    core_p = ParentedTree('CORE_P', [])
    nuc_p = ParentedTree('NUC_P', [])
    np1 = ParentedTree('NP', [])
    np2 = ParentedTree('NP', [])
    core_n = ParentedTree('CORE_N', [])
    if is_adjective(udnode):
        nuc_n1 = ParentedTree('NUC_A', [])
        nuc_n = ParentedTree('NUC_A', [])
    else:
        nuc_n1 = ParentedTree('NUC_N', [])        
        nuc_n = ParentedTree('NUC_N', [])        
    if is_personal_pronoun(udnode,language)  or is_indef_pronoun(udnode) or is_neg_pronoun(udnode,language):
        if is_clitic_pronoun(udnode,language):
            n = preterminal(udnode, 'PRO-CLT')
        elif is_neg_pronoun(udnode, language):
            n = preterminal(udnode, 'PRO-NEG')
        else:
            n = preterminal(udnode, 'PRO')
    elif is_determiner(udnode) or is_existential_there(udnode) or is_predeterminer(udnode) or is_dem_pronoun(udnode):
        n = preterminal(udnode, 'PRO-DEM')
    elif is_wh_pronoun(udnode) or is_wh_determiner(udnode):
        n = preterminal(udnode, 'PRO-WH')
        np2.label += '-WH' # todo refactor this?
    elif is_rel_pronoun(udnode) or is_rel_determiner(udnode):
        n = preterminal(udnode, 'PRO-REL')
        np2.label += '-REL' # todo refactor this?
    elif is_proper_noun(udnode):
        n = preterminal(udnode, 'N-PROP')
    elif is_adjective(udnode):
        n = preterminal(udnode, 'A')
    else:
        n = preterminal(udnode, 'N')
    nuc_n.append(n)
    nuc_n1.append(nuc_n)    
    core_n.append(nuc_n1)
    np2.append(core_n)
    np1.append(np2)
    core_p.append(np1)
    core_p.append(nuc_p)
    pp2.append(core_p)
    pp1.append(pp2)
    nuc2.append(pp1)
    nuc1.append(nuc2)
    core2.append(nuc1)
    core1.append(core2)
    clause2.append(core1)
    clause2.append(prcs)
    clause1.append(clause2)
    sentence2.append(clause1)
    sentence2.append(prdp)
    sentence1.append(sentence2)
    supercore.append(sentence1)
    punctuation = []
    attach_at_np_or_pp = []
    conjunctions_to_attach = []
    # recur
    current_conjunct = None
    again=True
    more_children=[]
    children=udnode.children
    while again:
        again=False
        if more_children:
            children=more_children
            udnode.children+=more_children
        more_children=[]
        for child in reversed(children):
            if child.token['deprel'] in ('acl','acl:relcl'):
                if is_adjective(child):
                    adjectival_clause = transform(child, language, layer='XP')
                elif is_verb(child):
                    if udnode.token['xpostag']=='WP':
                        adjectival_clause=transform(child, language)
                        n.label='PRO-WH'
                        np1.label='NP-WH'
                        np2.label='NP-WH'
                        if precedes_subject(udnode,udnode,language):
                            # only if this hasn't been moved already
                            if np1.parent.label=='CORE_P':
                                adjectival_clause.append(ParentedTree('PrCS',[np1.detach()]))
                        else:
                            if np1.parent.label=='CORE_P':
                                adjectival_clause.append(ParentedTree('PrCS',[np1.detach()]))                            
                    else:
                        adjectival_clause = peri(transform(child,language, layer='CLAUSE'))
                        #adjectival_clause = transform_A(child, language, layer='XP')
                elif is_coordinating_conjunction(child):
                    # this is certainly a parsing error (see fr 91)
                    adjectival_clause = transform_A(child,  language, layer='XP')
                else:
                    if (is_preposition(child) or is_subordinating_conjunction) and child.children:
                        more_children+=child.children
                        child.children=[]
                    adjectival_clause = transform(child, language, layer='CORE')
                if not is_marked_as_argument(child):
                    adjectival_clause = peri(adjectival_clause)
                if not is_verb(child):
                    core_n.append(adjectival_clause)
                else:
                    # relative clause
                    # there are problems here when the current N is a rel_pronoun (the verb should be its head)
                    if not udnode.token['xpostag']=='WP':
                        nuc_n.append(adjectival_clause)
                    else:
                        #nuc_n.append(adjectival_clause)
                        core_p.append(adjectival_clause)
            elif child.token['deprel'] in ('advcl','advcl:cleft'):
                if is_preposition(child) and child.children:
                    more_children+=child.children
                    child.children=[]
                adverbial_clause = transform(child, language, layer='CORE')
                if not is_marked_as_argument(child):
                    adverbial_clause = peri(adverbial_clause)
                core2.append(adverbial_clause)
            elif child.token['deprel'].startswith('advmod'):
                if is_neg_particle(child,language):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    core2.append(transform_NEG_OP(child, language))
                else:
                    adverbial_modifier = peri(transform_ADV(child, language))
                    if precedes_subject(child, udnode,language):
                        clause2.append(adverbial_modifier)
                    else:
                        #core_n.append(adverbial_modifier)
                        if is_core_adverb(child,language):
                            core2.append(adverbial_modifier)
                        elif is_root_adverb(child,language):
                            attach_at_np_or_pp+=[adverbial_modifier]
                        else:
                            #if layer_priority(layer)<4:
                            nuc2.append(adverbial_modifier)
                            
            elif child.token['deprel'].startswith('amod') or child.token['deprel'] in ('acl','compound:prt'):
                if is_noun(child):
                    compound = transform(child, language, layer='X')
                    nuc_n.append(compound)
                elif is_verb(child) and (is_gerund_or_present_participle(child) or is_past_participle(child)):
                    core_n.append(peri(transform_A(child, language)))                    
                else:
                    core_n.append(peri(transform(child, language)))
            elif child.token['deprel'] in ('appos', 'dep'):
                if is_cardinal(child):
                    core_n.append(peri(transform_N(child, language)))
                else:
                    # at least for sentence 1578(en)
                    np1.append(transform(child,language,layer='XP'))
                    #core_n.append(peri(transform(child, language)))
            elif child.token['deprel'] == 'aux':
                if child.children:
                    more_children+=child.children
                    child.children=[]
                if is_modal(child,language):
                    core2.append(transform_MOD_OP(child, language))
                else:
                    clause2.append(transform_TNS_OP(child, language))
            elif child.token['deprel'] in ('case','fixed','case:det'):
                if is_preposition(child) or is_to(child) or is_coordinating_conjunction(child) or is_determiner(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    if language=='fr' and child.token['lemma']=='Oe':
                        # for O'Brien
                        nuc_n.append(transform_P(child,language))
                    else:
                        nuc_p.append(transform_P(child, language))
                elif is_possessive_ending(child):
                    np2.append(transform_possessive_ending(child, language))
                elif is_verb(child):
                    supercore.append(transform(child, language, layer='NUC'))
                    # Simon: added this (probably no sense)
                elif is_adjective(child):
                    core_n.append(peri(transform(child, language)))
                elif is_particle(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    #core_n.append(peri(transform(child, language)))
                    nuc_p.append(transform_P(child, language))
                elif is_adverb(child):
                    # "dazu die Stellen"
                    np2.append(transform_ADV(child,language))
                elif is_noun(child):
                    core_p.append(peri(transform(child, language)))
                elif is_subordinating_conjunction(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    core2.append(transform_CLM(child, language))
                elif is_punctuation(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    punctuation.append(transform(child, language))
                elif is_personal_pronoun(child, language):
                    core_p.append(peri(transform(child, language)))
                else:
                    raise NotHandled(child)
            elif child.token['deprel'] in ('cc','cc:preconj'):
                if child.children:
                    more_children+=child.children
                    child.children=[]
                coordinating_conjunction = transform_CLM(child, language)
                if is_coordinating_conjunction(child):
                    # here we should check and get the same conjunct as for the conj dependency
                    # nuc_n or np
                    # here we chose only depending on whether the n is a bare n or not
                    if is_bare(pp2):
                        if is_bare(np2): 
                            current_conjunct=nuc_n
                        else:
                            current_conjunct=np2
                    else:
                        # here should be pp2 but somehow it works worse
                        current_conjunct=np2
                else:
                    current_conjunct=np2
                #current_conjunct=attach_coordinating_conjunction(coordinating_conjunction, n, current_conjunct)
                conjunctions_to_attach+=[(coordinating_conjunction,current_conjunct)]
                
            elif child.token['deprel'] in ('compound','compound:lvc') or child.token['deprel'].startswith('flat'):
                if child.children:
                    more_children += child.children
                    child.children = []
                compound = transform(child, language, layer='X')
                if is_cardinal(child):
                    core_n.append(compound)
                elif is_verb(child):
                    core_n.append(compound.detach())
                else:
                    # maybe only for flat (Große Bruder, Winston Smith)
                    nuc_n.append(compound)
            elif child.token['deprel'] in ('compound:redup',):
                compound = transform_N(child, language, layer='X')
                nuc_n.append(compound)
            elif child.token['deprel'] in ('conj', 'discourse', 'parataxis','vocative','dislocated'):
                if is_noun_or_proper_noun(child):
                    if is_proper_noun(child):
                        conjunct = transform_N(child, language)#preterminal(child, 'N-PROP')
                    else:
                        conjunct = transform_N(child, language)#preterminal(child, 'N')
                    # we should attach at the nuc_n, and when not possible (because of adjectives)
                    # try at the np

                    # this helps for sentence 30(de), but somehow seems to break other things
                    #if not has_above(conjunct,'NUC_N'):
                    #    conjunct=transform_N(child, language,layer='NUC_N')
                    # if not attach_conjunct(conjunct,nuc_n):
                    #     conjunct.detach()
                    #     attach_conjunct(conjunct,np2)
                    #     current_conjunct='NP'
                    # else:
                    #     current_conjunct = 'NUC_N'
                    # does not work yet 

                    # if not is_bare(np2) or not has_above(conjunct,'NUC_N'):
                    #     attach_conjunct(conjunct,np2)
                    #     current_conjunct='NP'
                    # else:
                    #     leaf=one_leaf(conjunct)
                    #     trim(conjunct,'NUC_N')
                    #     conjunct=root(leaf)
                    #     attach_conjunct(conjunct,nuc_n)
                    #     current_conjunct = 'NUC_N'
                    if not is_proper_noun(udnode) and not has_above(conjunct,'NUC_N') :
                        leaf=one_leaf(conjunct)
                        trim(conjunct,'NUC_N')
                        conjunct=root(leaf)
                        attach_conjunct(conjunct,nuc_n)
                        current_conjunct='NUC_N'
                    else:
                        attach_conjunct(conjunct,np2)
                        current_conjunct='NP'




                else:
                    if is_adjective(child):
                    #probably an error in parsing
                        conjunct = transform_A(child,language,layer='AP')
                        nuc2.append(conjunct)
                    elif is_verb(child):
                        conjunct = transform_V(child,language,layer='CLAUSE')
                        attach_conjunct(conjunct,np2)
                    else:
                        conjunct = transform_N(child, language)
                        attach_conjunct(conjunct, n)
                        current_conjunct = conjunct
            elif child.token['deprel'] in ('cop', 'auxpass','aux:pass'):
                if has_expl(udnode,language) and not further_cop(child,udnode,language):
                    verb_tree=transform_V(child,language,'NUC')
                    core2.append(verb_tree)
                    # for nuc_child in nuc2.children:
                    #     core2.append(nuc_child.detach())
                    # for nuc_child in nuc1.children[0].children:
                    #     core2.append(nuc_child.detach())
                    for nuc_child in nuc1.children:
                        for nuc_grandchild in nuc_child.children.copy():
                            core2.append(nuc_grandchild.detach())
                    nuc1.detach()
                    nuc2=core2
                    nuc1=core1
                elif udnode.token['xpostag']=='WP':
                    # "what is it?" (is-cop, it-nsubj)
                    # -> move the np of "what" to the prcs
                    nuc2.append(transform_AUX(child, language))
                    if precedes_subject(udnode,udnode,language):
                        prcs.append(pp1.detach())
                    np1.label='NP-WH'
                    np2.label='NP-WH'
                    n.label='PRO-WH'
                else:
                    nuc2.append(transform_AUX(child, language))
            elif child.token['deprel'] == 'csubj':
                core2.append(transform(child, language, layer='CORE'))
            elif child.token['deprel'] in ('det','det:poss', 'det:predet', 'nmod:poss'):
                if is_neg_determiner(child):
                    if language in ('de',):
                        # 'kein' is OP-NEG at the CORE-N level
                        core_n.append(transform_determiner(child, language))
                    else:
                        np2.append(transform_determiner(child, language))
                elif is_rel_pronoun(child):
                    np2.append(transform_N(child, language))
                    make_rel(np2)
                elif is_rel_determiner(child):
                    np2.append(transform_determiner(child, language))
                    make_wh(np2)
                elif is_cardinal(child):
                    np2.append(transform_QNT(child,language))
                elif is_adverb(child):
                    adverbial_modifier = peri(transform_ADV(child, language))
                    if precedes_subject(child, udnode,language):
                        clause2.append(adverbial_modifier)
                    else:
                        nuc2.append(adverbial_modifier)
                elif is_existential_there(child):
                    core2.append(transform(child,language))
                elif is_verb(child):
                    nuc2.append(transform(child,language))
                else:
                    if not is_noun(child) and child.children:
                        more_children+=child.children
                        child.children=[]
                    np2.append(transform_determiner(child, language))
            elif child.token['deprel'] == 'mark':
                if child.children:
                    more_children+=child.children
                    child.children=[]
                if is_particle(child) and child.token['xpostag']=='PTKZU':
                    nuc2.append(transform_CLM(child, language))
                elif child.token['lemma']=='to' or child.token['xpostag']=='KOUI':
                    core2.append(transform_CLM(child, language))
                else:
                    clause2.append(transform_CLM(child, language))
                    
            elif child.token['deprel'] == 'neg':
                core2.append(transform_NEG_OP(child, language))
            elif child.token['deprel'] in ('nsubj', 'nsubjpass','nsubj:pass', 'expl', 'dobj', 'iobj','obj'):
                if (is_wh_pronoun(child) or is_wh_determiner(child) or is_rel_pronoun(child) or is_rel_determiner(child)):
                    prcs.append(transform(child, language))
                elif child.token['upostag']=='PRON':
                    #prcs.append(transform(child, language))
                    core2.append(transform(child, language))
                else:
                    core2.append(transform(child, language))
            elif child.token['deprel'].startswith('nmod') or child.token['deprel'] in ('obl','obl:tmod','obl:npmod','obl:agent','obl:mod'):
                if is_neg_determiner(child):
                    core_n.append(transform_determiner(child, language))
                elif is_noun(child) and is_genitive(child) and precedes(child,udnode,language):
                    np2.append(transform_N_determiner(child,language))

                else:
                    if is_preposition(child):
                        if child.children:
                            more_children+=child.children
                            child.children=[]
                        nominal_modifier = transform_P(child, language, layer='XP')
                    elif is_verb(child):
                        nominal_modifier = transform_V(child, language)
                    elif is_adverb(child):
                        nominal_modifier = transform_ADV(child, language)
                    else:
                        nominal_modifier = transform_N(child, language)
                        #if not is_marked_as_argument(child, ptbtree):
                        # this should happen sometimes: maybe only for nmod and not for obl?
                        #if child.token['deprel'].startswith('nmod'):
                        #    nominal_modifier = peri(nominal_modifier)
                    if precedes_subject(child, udnode,language):
                        prdp.append(nominal_modifier)
                    # elif precedes(child,udnode,language):
                    #     prdp.append(nominal_modifier)
                        
                    else:
                        if is_marked_as_argument(child):
                            core_n.append(nominal_modifier)
                        else:
                            core_n.append(peri(nominal_modifier))
            elif child.token['deprel'] == 'obl:arg':
                # L4: replica bajo cabeza NOMINAL el dispatch que L3 anadio a
                # transform_V para obl:arg (dativo/nominalizaciones). MISC
                # manda; sin MISC, fallback es: clitico atono -> AGX, si no ->
                # argumento del CORE. Otras lenguas sin MISC: NotHandled (este
                # deprel nunca estaba en el dispatch de transform_N).
                rrg_misc = child.token.get('misc') or {}
                rrg_role = rrg_misc.get('RRGRole')
                if rrg_role == 'AGX' or (rrg_role is None and language == 'es' and is_clitic_pronoun(child, language) and not _es_conllu_analizado(udnode)):
                    nuc_n1.append(preterminal(child, 'AGX'))
                elif rrg_role in ('CoreArg', 'Periphery') or (rrg_role is None and language == 'es'):
                    if is_preposition(child):
                        if child.children:
                            more_children += child.children
                            child.children = []
                        nominal_modifier = transform_P(child, language, layer='XP')
                    else:
                        nominal_modifier = transform_N(child, language, layer='XP')
                    if rrg_role == 'Periphery':
                        # Etapa PERIFERIA (Julian 2026-07-13): anclaje
                        # scope-driven vía RRGStratum -- reemplaza el viejo
                        # "temporal siempre CLAUSE" de L3.
                        nominal_modifier = peri(nominal_modifier)
                        estrato = rrg_misc.get('RRGStratum', 'centro')
                        if estrato == 'clausula':
                            clause2.append(nominal_modifier)
                        elif estrato == 'nucleo':
                            nuc_n.append(nominal_modifier)
                        else:
                            core_n.append(nominal_modifier)
                    else:
                        core_n.append(nominal_modifier)
                else:
                    raise NotHandled(child)
            elif child.token['deprel'] in ('nummod','nummod:gov'):
                core_n.append(transform(child, language, layer='XP'))
            elif child.token['deprel'] == 'punct':
                if child.children:
                    more_children+=child.children
                    child.children=[]
                punctuation.append(transform(child, language))
                #layer='SENTENCE'
            elif child.token['deprel'] == 'xcomp':
                open_clausal_complement = transform(child, language, layer='SENTENCE')
                linkage.core_sub(sentence1, sentence2, clause1, clause2, core1,
                                 core2, nuc1, nuc2, open_clausal_complement)
            # probably a dependency parsing error
            elif child.token['deprel'].startswith('ccomp'):
                clausal_complement = transform(child, language, layer='SENTENCE')
                linkage.clause_sub(sentence1, sentence2, clause1, clause2, core1,
                    core2, nuc1, nuc2, clausal_complement)
            else:
                raise NotHandled(child)
        if more_children:
            again=True

    # if there is no NUC_P, there should be no CORE_P:
    if not nuc_p.children:
        core_p.detach()
        for child in core_p.children.copy():
            pp2.append(child.detach())        

            
    economize(prdp)
    economize(prcs)
    economize(nuc_p)
    conflate(supercore, sentence1)
    conflate(sentence1, sentence2)
    conflate(clause1, clause2)
    conflate(core1, core2)
    conflate(core2, pp1)
    conflate(nuc1, nuc2)
    conflate(pp1, pp2)
    conflate(pp2, np1)
    conflate(np1, np2)
    conflate(nuc_n1,nuc_n)
    if is_personal_pronoun(udnode,language) or is_dem_pronoun(udnode) or is_determiner(udnode) or is_predeterminer(udnode) or is_wh_pronoun(udnode) or is_wh_determiner(udnode) or is_rel_pronoun(udnode) or is_rel_determiner(udnode) or is_existential_there(udnode) or is_neg_pronoun(udnode,language):
        conflate(core_n, n)
    trim(sentence2, layer)
    tree = root(n)
    if len(np1) > 0:
        conflate(tree, np1)
    else:
        conflate(tree, np2)
    tree = root(n)
    if punctuation:
        # this seems buggy: in some cases add_punctuation adds weird nodes (such as NUC_N-PROP over N_PROP)
        linkage.add_punctuation(tree, punctuation)
    if attach_at_np_or_pp:
        for subtree in attach_at_np_or_pp:
            tree.append(subtree)
    if conjunctions_to_attach:
        for (subtree,attachment_level) in conjunctions_to_attach:
            if attachment_level==nuc_n and nuc_n.children:
                attach_coordinating_conjunction(subtree,n,nuc_n)
            else:
                attach_coordinating_conjunction(subtree,n,root(n))

    tree=root(n)
    return tree


def transform_AUX(udnode, language):
    # make fragment
    aux = preterminal(udnode, 'AUX')
    if is_finite_verb(udnode):
        aux.label += '-TNS'
    # if there are children, it is probably not an auxiliary
    # (or the children are not valid)
    if udnode.children:
        return transform_V(udnode,language)
    # return
    return aux


def transform_MOD_OP(udnode, language):
    # make fragment
    tns_op = preterminal(udnode, 'OP-MOD')
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return tns_op


def transform_TNS_OP(udnode, language):
    # make fragment
    tns_op = preterminal(udnode, 'OP-TNS')
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return tns_op


def transform_ASP_OP(udnode, language):
    # make fragment
    asp_op = preterminal(udnode, 'OP-ASP')
    # recur
    for child in udnode.children:
        raise NotHandled(child)
    # return
    return asp_op


def transform_UH(udnode, language, layer='CLAUSE'):
    # make fragment
    sentence = ParentedTree('SENTENCE', [])
    clause = ParentedTree('CLAUSE', [])
    core = ParentedTree('CORE', [])
    nuc = ParentedTree('NUC', [])
    uh = preterminal(udnode, 'UH')
    nuc.append(uh)
    core.append(nuc)
    clause.append(core)
    sentence.append(clause)
    punctuation = []
    # recur
    again=True
    more_children=[]
    while again:
        again=False
        if more_children:
            udnode.children=more_children
        more_children=[]
        for child in udnode.children:
            if child.token['deprel'] in ('punct',):
                if child.children:
                    more_children+=child.children
                    child.children=[]
                punctuation.append(transform(child, language))
            elif child.token['deprel'] in ('advmod','conj','acl','nummod'):
                #parsing error for advmod, more like a conjunct?
                conjunct = transform(child, language)
                attach_conjunct(conjunct, clause)
            elif child.token['deprel'] in ('vocative',):
                core.append(transform(child, language, layer='XP'))
            else:
                raise NotHandled(child)
        if more_children:
            again=True    # return
    # return
    trim(sentence, layer)
    tree = root(uh)
    linkage.add_punctuation(tree, punctuation)
    return tree


def transform_V(udnode, language, layer='CLAUSE'):
    # make fragment
    sentence1 = ParentedTree('SENTENCE', [])
    sentence2 = ParentedTree('SENTENCE', [])
    prdp = ParentedTree('PrDP', [])
    clause1 = ParentedTree('CLAUSE', [])
    clause2 = ParentedTree('CLAUSE', [])
    prcs = ParentedTree('PrCS', [])
    core1 = ParentedTree('CORE', [])
    core2 = ParentedTree('CORE', [])
    nuc1 = ParentedTree('NUC', [])
    nuc2 = ParentedTree('NUC', [])
    if False:#is_past_participle(udnode):
        v = preterminal(udnode, 'V-PART')
    if False:#is_gerund_or_present_participle(udnode):
        v = preterminal(udnode, 'V-GER')
    else:
        v = preterminal(udnode, 'V')
    nuc2.append(v)
    nuc1.append(nuc2)
    core2.append(nuc1)
    core1.append(core2)
    clause2.append(core1)
    clause2.append(prcs)
    clause1.append(clause2)
    sentence2.append(clause1)
    sentence2.append(prdp)
    sentence1.append(sentence2)
    punctuation = []
    # recur
    current_conjunct = None
    again=True
    more_children=[]
    children=udnode.children
    while again:
        again=False
        if more_children:
            children=more_children
        more_children=[]
        for child in reversed(children):
            # use a copy in case the children list is modified (in case transformation has to be reset)
            child=copy.copy(child)
            # move this to a function
            # getting the adverbs wrongly attached to children
            # if is_noun(child):
            #     adverbs=[]
            #     new_grandchildren=[]
            #     for grandchild in child.children:
            #         if grandchild.token['deprel']=='advmod':
            #             print('Reaffect adverb')
            #             adverbs+=[grandchild]
            #         else:
            #             new_grandchildren+=[grandchild]
            #     child.children=new_grandchildren
            #     more_children+=adverbs

            

            
            if child.token['deprel'] in ('advcl'):
                if is_punctuation(child) or is_particle(child) or is_subordinating_conjunction(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                adverbial_clause = transform(child, language, layer='CORE')
                if not is_marked_as_argument(child):
                    adverbial_clause = peri(adverbial_clause)
                core2.append(adverbial_clause)
            elif child.token['deprel'].startswith('advmod'):
                if is_neg_particle(child,language):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    if language=='ru':
                        nuc2.append(transform_NEG_OP(child, language))                        
                    else:
                        core2.append(transform_NEG_OP(child, language))
                elif is_wh_adverb(child):
                    prcs.append(transform_ADV(child,language))
                    #elif is_adjective(child):
                    #wrong ud parse
                    #nuc2.append(transform_A(child,language))
                elif is_verb(child):
                    #wrong ud parse
                    if is_modal(child,language):
                        core2.append(transform_MOD_OP(child, language))
                    elif is_past_participle(child):
                        nuc2.append(transform_ASP_OP(child, language))
                    elif is_infinitive(child) and is_gerund_or_present_participle(udnode):
                        if child.children:
                            more_children+=child.children
                            child.children=[]
                        nuc2.append(transform_ASP_OP(child, language))
                    elif is_auxiliary(child):
                        if child.children:
                            more_children+=child.children
                            child.children=[]
                        nuc2.append(transform_AUX(child, language))
                    else:
                        if child.children:
                            more_children+=child.children
                            child.children=[]
                        clause2.append(transform_TNS_OP(child, language))
                else:
                    if precedes_subject(child, udnode,language):
                        prdp.append(transform_ADV(child, language))
                    else:
                        if is_prt_adverb(child,language):
                            nuc2.append(transform_PRT(child, language))
                        elif is_nuc_adverb(child,language):
                            if child.children:
                                more_children=child.children
                                child.children=[]
                            nuc2.append(transform_ADV(child, language,layer='ADV'))
                        else:
                            rrg_misc = child.token.get('misc') or {}
                            # L4.5 S2: periferia temporal INICIAL destacada
                            # (Etapa 1: destacado_inicial) -> PrDP (posicion
                            # dislocada izquierda, LDP), NO -PERI@CLAUSE. Esta
                            # rama solo se alcanza cuando precedes_subject()
                            # (heuristica sintactica generica, arriba) NO
                            # detecto el patron (p.ej. sujeto pro-drop, sin
                            # hermano nsubj que comparar) pero Etapa 1 SI
                            # marco destacado_inicial=True. La maquinaria PrDP
                            # ya existia (ver linea de arriba); esto solo la
                            # hace alcanzable via MISC cuando la heuristica
                            # generica no dispara.
                            if (language == 'es' and rrg_misc.get('RRGRole') == 'Periphery'
                                    and rrg_misc.get('RRGType') == 'temporal'
                                    and rrg_misc.get('RRGDetached') == 'si'):
                                prdp.append(transform_ADV(child, language))
                            else:
                                adverbial = peri(transform_ADV(child, language))
                                # Etapa PERIFERIA (Julian 2026-07-13): anclaje
                                # scope-driven vía RRGStratum (nucleo/centro/
                                # clausula) -- reemplaza el viejo "temporal
                                # siempre CLAUSE" de L3. Sin MISC/lengua
                                # distinta de 'es': comportamiento heredado
                                # (CORE).
                                if language == 'es' and rrg_misc.get('RRGRole') == 'Periphery':
                                    estrato = rrg_misc.get('RRGStratum', 'centro')
                                    if estrato == 'clausula':
                                        clause2.append(adverbial)
                                    elif estrato == 'nucleo':
                                        nuc2.append(adverbial)
                                    else:
                                        core2.append(adverbial)
                                else:
                                    core2.append(adverbial)
            elif child.token['deprel'].startswith('amod') or child.token['deprel'] in ('acl','acl:relcl') :
                #probably a parsing error:
                if is_verb(child):
                    aux_mod = transform_AUX(child, language)
                    #nuc2.append(aux_mod)
                    clause2.append(aux_mod)
                else:
                    if is_preposition(child):
                        if child.children:
                            more_children+=child.children
                            child.children=[]
                    adjectival_modifier = transform(child, language, layer='X')
                    nuc1.append(adjectival_modifier)
            elif child.token['deprel'] in ('aux', 'dep','cop'):
                if is_modal(child,language):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    core2.append(transform_MOD_OP(child, language))
                    #elif is_past_participle(child):                
                elif is_past_participle(child) or (child.token['lemma'] in ('have','\'ave') and is_infinitive(child) and is_past_participle(udnode)):
                    # child past particple: been making, been using
                    # have lost, have forgotten? -> child.token['lemma']=='have' and is_past_participle(udnode) and 
                    if child.children:
                        more_children=child.children
                        child.children=[]
                    nuc2.append(transform_ASP_OP(child, language))
                elif is_infinitive(child) and is_gerund_or_present_participle(udnode):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    nuc2.append(transform_ASP_OP(child, language))
                elif is_neg_verb(child):
                    core2.append(transform_NEG_OP(child, language))
                elif is_auxiliary(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    # do something about subjunctive (sei) -> should be AUX-MOD
                    if is_subjunctive(child):
                        core2.append(transform_MOD_OP(child, language))
                    elif is_neg_auxiliary(child):
                        core2.append(transform_NEG_OP(child, language))
                    elif (child.token['deprel']=='aux' and not is_participle(child)):
                        clause2.append(transform_TNS_OP(child, language))
                    else:
                        nuc2.append(transform_AUX(child, language))


                elif is_personal_pronoun(child,language) or is_dem_pronoun(child):
                    clause2.append(transform_N(child,language))
                else:
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    clause2.append(transform_TNS_OP(child, language))
            elif child.token['deprel'] in ('auxpass','aux:pass','aux:caus'):
                if is_past_participle(child):
                    passive_auxiliary = transform_ASP_OP(child, language)
                else:
                    passive_auxiliary = transform_AUX(child, language)
                nuc2.append(passive_auxiliary)
            elif child.token['deprel'] in ('cc','cc:preconj'):
                if child.children:
                    more_children+=child.children
                    child.children=[]
                coordinating_conjunction = transform_CLM(child, language)
                attach_coordinating_conjunction(coordinating_conjunction, v, current_conjunct)
            elif child.token['deprel'].startswith('ccomp'):
                if is_wh_pronoun(child) or is_rel_pronoun(child):
                    #probably a parsing error
                    prcs.append(transform_N(child,language))
                elif is_adverb(child):
                    core2.append(transform_ADV(child,language))
                else:
                    if is_preposition(child) and child.children:
                        more_children+=child.children
                        child.children=[]
                    clausal_complement = transform(child, language, layer='SENTENCE')
                    if is_topicalized(child):
                        prdp.append(linkage.reduce_to(clausal_complement, linkage.CLAUSE))
                    else:
                        if not has_clause(clausal_complement):
                            # -> should be a PP-rooted tree
                            clausal_complement.label='PP'
                            core2.append(clausal_complement)

                        # TODO: Solutions for other language than English
                        elif udnode.token['lemma'] in say_hyponyms \
                           or udnode.token['lemma'] in conjecture_hyponyms \
                           or udnode.token['lemma'] in care_hyponyms \
                           or udnode.token['lemma'] in consider_hyponyms \
                           or language!='en':
                            linkage.clause_sub(sentence1, sentence2, clause1, clause2,
                                           core1, core2, nuc1, nuc2, clausal_complement)
                        else:
                            linkage.core_sub(sentence1, sentence2, clause1, clause2,
                                             core1, core2, nuc1, nuc2, clausal_complement)
            elif child.token['deprel'] in ('conj', 'discourse', 'parataxis'):
                if is_preposition(child) or child.token['xpostag']=='MD' or is_interjection(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                if  child.token['xpostag']=='MD':
                    clause2.append(transform_TNS_OP(child,language))
                else:
                    conjunct = transform(child, language)
                    attach_conjunct(conjunct, v)
                    current_conjunct = conjunct
            elif child.token['deprel'] in ('csubj', 'csubjpass', 'csubj:pass'):
                core2.append(transform(child, language, layer='CORE'))
            elif child.token['deprel'] == 'mark':
                if is_adverb(child) and child.token['lemma']=='parce':
                    # this happens for 'parce' in French (so not an adverb but a conjunction)
                    #core2.append(peri(transform_ADV(child, language)))
                    if child.children:
                        # 'que' is probably there as a SCONJ
                        more_children+=child.children
                        child.children=[]
                    core2.append(transform_CLM(child, language))
                    
                else:    
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                        # maybe finer than this (only PTKZU and only for infinitive verbs)
                        # zu PTKZU -> NUC, zu PTKVZ -> CORE
                    if is_particle(child) and child.token['xpostag']=='PTKZU':
                        nuc2.append(transform_CLM(child, language))                
                    else:
                        if child.token['lemma']=='to' or child.token['xpostag']=='KOUI':
                            core2.append(transform_CLM(child, language))
                        else:
                            #core2.append(transform_CLM(child, language))
                            clause2.append(transform_CLM(child, language))
            elif child.token['deprel'] == 'mwe':
                nuc2.append(transform(child, language, layer='X'))
            elif child.token['deprel'] == 'neg':
                core2.append(transform_NEG_OP(child, language))
            elif child.token['deprel'].startswith('nmod') or child.token['deprel'] in ('obl','obl:tmod','obl:npmod','obl:agent'):
                if is_preposition(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    nominal_modifier = transform_P(child, language, layer='XP')
                elif is_cardinal(child):
                    nominal_modifier = transform_QNT_referential(child, language, layer='XP')
                elif is_verb(child):
                    # wrong dependency parsing (should be xcomp)
                    open_clausal_complement = transform(child, language, layer='SENTENCE')
                    if (udnode.token['lemma'] in begin_hyponyms
                        or udnode.token['lemma'] in sustain_hyponyms
                        or udnode.token['lemma'] in stop_hyponyms) \
                        and is_gerund_or_present_participle(child):
                        linkage.nuc_cosub(sentence1, sentence2, clause1, clause2, core1,
                                          core2, nuc1, nuc2, open_clausal_complement) 
                    else:
                        # in case the verb was transformed as a NP
                        if not has_clause(open_clausal_complement):
                            # -> should be a PP-rooted tree
                            open_clausal_complement.label='PP'
                            core2.append(open_clausal_complement)
                        else:
                            linkage.core_cosub(sentence1, sentence2, clause1, clause2, core1,
                                           core2, nuc1, nuc2, open_clausal_complement)
                else:
                    # for "of course", treated as an ADVP-PERI
                    if is_multi_word_adverb(child):
                        nominal_modifier = transform_ADV(child, language,layer='XP')
                    else:
                        nominal_modifier = transform_N(child, language,layer='XP')
                    # this should not happen in German (for obl at least)
                if not is_verb(child):
                    if precedes_subject(child, udnode,language):
                        prdp.append(nominal_modifier)
                    elif is_rel_pronoun(child):
                        # the PP root should be PP-REL
                        make_rel(nominal_modifier)
                        prcs.append(nominal_modifier)
                    else:
                        rrg_misc = child.token.get('misc') or {}
                        if (language == 'es' and rrg_misc.get('RRGRole') == 'Periphery'
                                and rrg_misc.get('RRGType') == 'temporal'
                                and rrg_misc.get('RRGDetached') == 'si'):
                            # L4.5 S2: periferia temporal INICIAL destacada
                            # (LDP) -> PrDP, sin sufijo -PERI. Ver comentario
                            # gemelo en el bloque advmod de transform_V.
                            prdp.append(nominal_modifier)
                        elif language == 'es' and rrg_misc.get('RRGRole') == 'Periphery':
                            # Etapa PERIFERIA (Julian 2026-07-13): anclaje
                            # scope-driven vía RRGStratum -- reemplaza la
                            # regla L3 "temporal siempre CLAUSE" (doctrina
                            # corregida: el marco temporal ancla a CENTRO/
                            # CORE, no a CLÁUSULA; solo razón/concesión/
                            # condición/epistémico van a CLAUSE). peri() ya
                            # pone el sufijo -PERI.
                            nominal_modifier = peri(nominal_modifier)
                            estrato = rrg_misc.get('RRGStratum', 'centro')
                            if estrato == 'clausula':
                                clause2.append(nominal_modifier)
                            elif estrato == 'nucleo':
                                nuc2.append(nominal_modifier)
                            else:
                                core2.append(nominal_modifier)
                        elif language == 'es' and rrg_misc.get('RRGRole') == 'CoreArg':
                            core2.append(nominal_modifier)
                        # sin MISC (o lengua distinta de 'es'): comportamiento
                        # heredado, sin cambios (is_marked_as_argument siempre
                        # True hoy, asi que esto nunca llama a peri() aqui).
                        elif not is_marked_as_argument(child):
                            nominal_modifier = peri(nominal_modifier)
                        # for "of course", treated as an ADVP-PERI
                        elif is_multi_word_adverb(child):
                            clause2.append(peri(nominal_modifier))
                        else:
                            core2.append(nominal_modifier)
            elif child.token['deprel'] == 'obl:arg':
                # AnCora: dativo (clitico y/o sintagma pleno doblado), y
                # tambien otros obl:arg marcados por la Etapa 1. El MISC
                # manda (RRGRole=AGX|CoreArg|Periphery); sin MISC, fallback
                # es: clitico atono -> AGX, si no -> argumento del CORE.
                # Otras lenguas sin MISC: NotHandled (comportamiento previo,
                # este deprel nunca estaba en el dispatch).
                rrg_misc = child.token.get('misc') or {}
                rrg_role = rrg_misc.get('RRGRole')
                if rrg_role == 'AGX' or (rrg_role is None and language == 'es' and is_clitic_pronoun(child, language) and not _es_conllu_analizado(udnode)):
                    # (AGX <clitico>) bajo NUC, hermano del NUC que contiene
                    # PRED>V (nuc2 ya fue anadido a nuc1 en el esqueleto).
                    nuc1.append(preterminal(child, 'AGX'))
                elif rrg_role in ('CoreArg', 'Periphery') or (rrg_role is None and language == 'es'):
                    if is_preposition(child):
                        if child.children:
                            more_children += child.children
                            child.children = []
                        nominal_modifier = transform_P(child, language, layer='XP')
                    else:
                        nominal_modifier = transform_N(child, language, layer='XP')
                    if rrg_role == 'Periphery':
                        # Etapa PERIFERIA (Julian 2026-07-13): anclaje
                        # scope-driven vía RRGStratum -- reemplaza el viejo
                        # "temporal siempre CLAUSE" de L3.
                        nominal_modifier = peri(nominal_modifier)
                        estrato = rrg_misc.get('RRGStratum', 'centro')
                        if estrato == 'clausula':
                            clause2.append(nominal_modifier)
                        elif estrato == 'nucleo':
                            nuc2.append(nominal_modifier)
                        else:
                            core2.append(nominal_modifier)
                    else:
                        core2.append(nominal_modifier)
                else:
                    raise NotHandled(child)
            elif child.token['deprel'] in ('expl:pass', 'expl:impers'):
                # L4 (interpretacion teorica pendiente de validacion por
                # Julian): el "se" reflejo-pasivo/impersonal es morfema
                # clitico -> AGX bajo NUC, mismo analisis y mismo arbol
                # elemental que los dativos de L3 (nuc1, hermano del NUC que
                # contiene PRED>V). El nsubj:pass (si lo hay, caso pasiva
                # refleja) sigue su propio dispatch como NP argumento del
                # CORE, sin tocar (rama 'nsubj:pass' de mas abajo). Otras
                # lenguas: NotHandled (comportamiento previo, sin cambios).
                # L5 §1 (conciliación AGX): con MISC (gruxx analizó la oración)
                # el AGX se crea SOLO si la Etapa 1 lo marcó (RRGRole=AGX). Un
                # "se" pasivo/impersonal en una cláusula EMBEBIDA -- que el
                # mapper (solo cláusula principal) no analiza -- ya no inventa
                # un nodo AGX que la LS no anticipa (era la causa dominante de
                # 'árbol con más AGX que la LS'); cae a argumento del CORE. Sin
                # MISC (conllu crudo) se conserva el AGX de siempre.
                rrg_misc = child.token.get('misc') or {}
                if language == 'es' and (rrg_misc.get('RRGRole') == 'AGX'
                                         or not _es_conllu_analizado(udnode)):
                    nuc1.append(preterminal(child, 'AGX'))
                elif language == 'es':
                    core2.append(transform_N(child, language))
                else:
                    raise NotHandled(child)
            # added det here to treat it like a pronoun (when mistakes in dependencies), and case
            elif child.token['deprel'] in ('nsubj','nsubjpass','nsubj:pass','expl','det','det:poss','expl:pv'):
                rrg_misc = child.token.get('misc') or {}
                if language == 'es' and rrg_misc.get('RRGRole') == 'AGX':
                    # L4.5 S5: "se" ASPECTUAL (correferencial + verbo
                    # transitivo con obj, ver
                    # nucleo_periferia._detectar_se_aspectual) llega con
                    # deprel='expl:pv' -- el MISMO deprel que el reflexivo/
                    # anticausativo generico, que NO produce AGX (queda
                    # como PRO-CLT normal, rama 'else' de abajo). El MISC
                    # decide caso por caso. Mismo arbol elemental que los
                    # demas AGX (nuc1, hermano del NUC que contiene
                    # PRED>V).
                    nuc1.append(preterminal(child, 'AGX'))
                elif is_cardinal(child):
                    core2.append(transform_QNT_referential(child, language))
                elif is_wh_pronoun(child) or is_wh_determiner(child) or (is_determiner(child) and child.token['lemma']=='that'):
                    prcs.append(transform(child, language))
                elif is_adverb(child):
                    # maybe only for trotzdem, annotated as PRT
                    prcs.append(transform_ADV(child,language))
                elif is_preposition(child):
                    core2.append(transform(child,language))
                elif is_rel_pronoun(child):
                    prcs.append(transform_N(child,language))
                elif is_determiner(child) and is_gerund_or_present_participle(udnode) and child.token['deprel']=='det':
                    #return transform_N(udnode,language)
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    clause2.append(transform_determiner(child, language))
                    # relabel as we consider this verb as noun
                    # sometimes it should be adjective (as 1619)
                    clause2.label='NP'
                    clause1.label='NP'
                    core2.label='CORE_N'
                    core1.label='CORE_N'
                    nuc1.label='NUC_N'
                    nuc2.label='NUC_N'
                    v.label='V-GER'
                    
                elif child.token['lemma']=='yes':
                    # Here we should relabel the child to treat it as an adverb   
                    child.token['deprel']='advmod'
                    child.token['upostag']='RB'
                    more_children+=[child]
                    #elif udnode.token['lemma']=='say' and precedes_subject(child,udnode,language) and punctuation_between(child,udnode,language):
                elif udnode.token['lemma']=='say'  and punctuation_between(child,udnode,language):
                    # this should be more restrictive to prevent putting a real subject of say in a prdp
                    prdp.append(transform(child,language))
                    
                else:
                    core2.append(transform_N(child, language))

            elif child.token['deprel'] in ('case',):
                if child.token['lemma']=='to' or child.token['xpostag']=='KOUI':
                    # should this be only for infinitives?
                    core2.append(transform_CLM(child, language))
                elif is_preposition(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                    core2.append(transform(child,language))
                elif is_pronominal_adverb(child):
                    clause2.append(peri(transform(child,language)))
                elif is_particle(child):
                    core2.append(transform_P(child,language))
                elif is_possessive_ending(child):
                    nuc2.append(transform_possessive_ending(child,language))
                elif is_adjective(child):
                    clause2.append(transform_A(child,language))
                else:
                    raise NotHandled(child)

                    
            elif child.token['deprel'] in ('dobj','iobj','obj','obj:agent','iobj:agent'):
                rrg_misc = child.token.get('misc') or {}
                if language == 'es' and rrg_misc.get('RRGRole') == 'AGX':
                    # L5 §1 (conciliación AGX): clítico átono ACUSATIVO
                    # (me/te/nos/os en 'obj', o leísmo le/les) o dativo en
                    # 'iobj' marcado por la Etapa 1 -> AGX bajo NUC (nuc1,
                    # hermano del NUC con PRED>V), como los demás clíticos.
                    # El argumento se realiza morfológicamente en la LS (ver
                    # nucleo_periferia._detectar_agx / completeness). Solo con
                    # MISC 'es'; sin MISC el clítico sigue su ruta previa.
                    nuc1.append(preterminal(child, 'AGX'))
                elif is_cardinal(child):
                    core2.append(transform_QNT_referential(child, language))
                elif (is_wh_pronoun(child) or is_wh_determiner(child)):
                    prcs.append(transform(child, language))
                elif is_adverb(child):
                    # maybe only for trotzdem, annotated as PRT
                    prcs.append(transform_ADV(child,language))
                elif is_preposition(child):
                    core2.append(transform(child,language))
                elif is_rel_pronoun(child):
                    if precedes(child,udnode,language):
                        prcs.append(transform_N(child,language))
                    else:
                        clause2.append(transform_N(child,language))
                elif is_verb(child):
                    core2.append(transform_V(child,language))
                elif is_clitic_pronoun(child,language):
                    #if language == 'fr' and child.token['lemma'] == 'se':
                    if False:
                        # this should apply only in the case of reflexive verbs
                        nuc2.append(transform_N(child,language,'X'))
                    else:
                        core2.append(transform_N(child,language))
                        
                else:
                    core2.append(transform_N(child, language))

            elif child.token['deprel'] in ('compound:preverb'):
                if child.children:
                    more_children+=child.children
                    child.children=[]
                nuc2.append(transform(child, language))
            elif child.token['deprel'] in ('compound:prt'):
                if child.children:
                    more_children+=child.children
                    child.children=[]
                if is_particle(child) or is_preposition(child):
                    nuc2.append(transform_PRT(child, language))
                else:
                    #nuc2.append(transform(child, language))
                    core2.append(transform(child, language))
            elif child.token['deprel'] in ('compound:lvc','compound'):
                nuc2.append(transform(child, language))
            elif child.token['deprel'] == 'punct':
                if child.children:
                    more_children+=child.children
                    child.children=[]
                punctuation.append(transform(child, language))
                #layer='SENTENCE'
            elif child.token['deprel'] in ('xcomp','acl'):
                if is_coordinating_conjunction(child):
                    if child.children:
                        more_children+=child.children
                        child.children=[]
                if not is_adjective(child):
                    if is_subordinating_conjunction(child):
                        if child.children:
                            more_children+=child.children
                            child.children=[]
                    open_clausal_complement = transform(child, language, layer='SENTENCE')
                # wrong dependency parsing (ex 233.en)
                if not is_verb(child):
                    if is_adjective(child):
                        open_clausal_complement=transform_A(child,language)
                        nuc2.append(open_clausal_complement)
                    elif precedes_subject(child, udnode,language):
                        prdp.append(open_clausal_complement)
                    else:
                        # this should happen sometimes, but when?
                        if not is_marked_as_argument(child):
                            open_clausal_complement = peri(open_clausal_complement)
                        core2.append(open_clausal_complement)
                elif ( language=='en' and (udnode.token['lemma'] in begin_hyponyms
                    or udnode.token['lemma'] in sustain_hyponyms
                    or udnode.token['lemma'] in stop_hyponyms) \
                    and is_gerund_or_present_participle(child)) or \
                    (  language=='de' and udnode.token['lemma'] in ('lassen','bleiben')):
                    
                    linkage.nuc_cosub(sentence1, sentence2, clause1, clause2, core1,
                    core2, nuc1, nuc2, open_clausal_complement) 
                elif (language=='en' and udnode.token['lemma']=='seem') or (language=='de' and udnode.token['lemma'] in ('scheinen','glauben') and precedes(udnode,child,language)):
                    linkage.core_coord(sentence1, sentence2, clause1, clause2, core1,
                                       core2, nuc1, nuc2, open_clausal_complement)
                else:
                    if not has_clause(open_clausal_complement):
                        clause2.append(open_clausal_complement)
                    else:
                        linkage.core_cosub(sentence1, sentence2, clause1, clause2, core1,
                                       core2, nuc1, nuc2, open_clausal_complement)
            elif child.token['deprel'] in ('appos', 'dep'):
                if is_cardinal(child):
                    clause1.append(peri(transform_N(child, language)))
                elif is_noun(child):                    
                    #clause1.append(peri(transform_N(child, language)))
                    core2.append(transform_N(child, language))
                else:
                    clause1.append(peri(transform(child, language)))
            elif child.token['deprel'] in ('nummod', 'nummod:gov'):
                core2.append(transform(child, language, layer='XP'))
            elif child.token['deprel'] in ('fixed',):
                if is_subordinating_conjunction(child):
                    core2.append(transform_CLM(child, language))
    
                else:
                    core2.append(transform(child, language, layer='XP'))
            elif child.token['deprel'] in ('vocative',):
                core2.append(transform(child, language))
            elif child.token['deprel'] in ('flat',):
                core2.append(transform(child, language))
            elif child.token['deprel'] in ('dislocated',):
                core2.append(transform(child,language))
            else:
                raise NotHandled(child)
        if more_children:
            again=True    # return
            
    economize(prdp)
    economize(prcs)
    conflate(sentence1, sentence2)
    conflate(clause1, clause2)
    conflate(core1, core2)
    conflate(nuc1, nuc2)
    trim(sentence2, layer)
    tree = root(v)
    linkage.add_punctuation(tree, punctuation)
    return tree


def transform_determiner(udnode, language, **options):
    if is_predeterminer(udnode):
        return transform_PDT(udnode, language, **options)
    if is_determiner(udnode) or is_possessive_pronoun(udnode) or is_predeterminer(udnode) or is_indef_pronoun(udnode) or is_dem_pronoun(udnode):
        if is_neg_determiner(udnode):
            # kein is OP-NEG, no is OP-NEG
            if language in ('de',):
                return transform_NEG_OP(udnode,language, **options)
            else:
                return transform_DEF_OP(udnode,language, **options)
        else:
            return transform_DEF_OP(udnode, language, **options)
    elif is_noun(udnode) or is_personal_pronoun(udnode,language)  or is_wh_pronoun(udnode) or is_wh_determiner(udnode) or is_proper_noun(udnode):
        if is_neg_determiner(udnode):
            return transform_DEF_OP(udnode,language, **options)
            #return transform_NEG_OP(udnode,language, **options)
        return transform_N_determiner(udnode, language, **options)
    elif is_preposition(udnode):
        # not sure about that (for aux in fr for example)
        return transform_DEF_OP(udnode, language, **options)
    elif is_adjective(udnode):
        # not sure about that (for certain in fr for example)
        return transform_A(udnode, language, **options)
    elif is_cardinal(udnode):
        return transform_QNT_referential(udnode, language, **options)
    raise NotHandled(udnode)


def _normalize_xpos_es(udnode):
    # AnCora/Freeling XPOS usa un tagset en minusculas (p.ej. 'vmis3s0') que
    # nunca matchea los tagsets en mayuscula (Penn/STTS) que asumen is_verb,
    # is_noun, is_adjective, is_adverb, is_preposition, etc.: el chequeo
    # "if(udnode.token['xpostag'])" es verdadero (la cadena no esta vacia)
    # pero ningun 'in'/'startswith' matchea nunca, asi que la clasificacion
    # cae silenciosamente a False y el dispatch entero termina en
    # NotHandled. Poniendo xpostag/xpos a None se fuerza el fallback a UPOS
    # (universal, no depende de tagset) para TODO el subarbol de una sola
    # pasada: exactamente lo que limpiar_conllu_stanza ya hace en el
    # pipeline "limpio" (ver CHECKPOINT_L0_L2.md L0), pero aqui tambien
    # cubre el gold crudo. Mutacion in-place: 'form'/'upostag'/'feats' (los
    # unicos campos que usa add_traces_to_rrg_from_ud.py) no se tocan.
    udnode.token['xpostag'] = None
    udnode.token['xpos'] = None
    for child in udnode.children:
        _normalize_xpos_es(child)


def transform(udnode,  language, **options):
    # Se dispara una sola vez por oracion: el nodo raiz UD es el unico con
    # deprel=='root'. Gated estrictamente por language=='es' (REGLA DE ORO):
    # en/de/fr/ru/fa no ejecutan esta rama, comportamiento byte-identico.
    if language == 'es' and udnode.token['deprel'] == 'root':
        _normalize_xpos_es(udnode)
    if is_verb(udnode) or is_modal(udnode,language):
        return transform_V(udnode, language, **options)
    if is_noun(udnode) or is_personal_pronoun(udnode,language) or is_dem_pronoun(udnode) or is_wh_pronoun(udnode) or is_rel_pronoun(udnode) or is_indef_pronoun(udnode) or is_wh_determiner(udnode) or is_existential_there(udnode) or is_proper_noun(udnode):
        if udnode.token['lemma']=='yes':
            return transform_ADV(udnode, language, **options)        
        else:
            return transform_N(udnode, language, **options)
    if is_adjective(udnode):
        return transform_A(udnode, language, **options)
    if is_adverb(udnode):
        return transform_ADV(udnode, language, **options)
    if is_cardinal(udnode):
        if udnode.token['deprel'] == 'root':
            return transform_QNT_referential(udnode, language, **options)
        else:
            return transform_QNT(udnode, language, **options)
    if is_particle(udnode):
        return transform_PRT(udnode, language,**options)
    if is_preposition(udnode) or is_to(udnode):
        if udnode.token['deprel'] == 'root':
            return transform_P_root(udnode, language, **options)
        else:
            return transform_P(udnode, language, **options)
    if is_to(udnode):
        return transform_CLM(udnode, language, **options)
    if is_punctuation(udnode):
        if udnode.token['deprel'] == 'root':
            return transform_punctuation_root(udnode, language, **options)
        else:
            return transform_punctuation(udnode, language, **options)
    if is_interjection(udnode):
        if udnode.token['deprel'] == 'root':
            # consider the interjection as a noun (ex: 2245 en)
            return transform_N(udnode, language, **options)
        else:
            return transform_UH(udnode, language, **options)
    if is_determiner(udnode) or is_predeterminer(udnode):
        return transform_N(udnode, language, **options)
    if is_coordinating_conjunction(udnode):
        if udnode.token['deprel'] == 'root':
            return transform_P_root(udnode, language, **options)
        else:
            return transform_P(udnode, language, **options)
    if is_subordinating_conjunction(udnode):
        return transform_CLM(udnode, language, **options)
    if udnode.token['xpostag']=='MD':
        # happens sentence 5353 en
        return transform_N(udnode, language, **options)
    if udnode.token['upostag']=='AUX':
        # for things wrongly tagged as auxiliaries
        return transform_V(udnode, language, **options)
    if udnode.token['upostag']=='PRON':
        return transform_N(udnode, language, **options)        
    raise NotHandled(udnode)


### MAIN ######################################################################


def ud2rrg(udtree, language):
    # [sent] stores sentence tokens
    # sent is needed to get the order of the tokens right.
    sent = []
    #print("Serialize:")
    #print(str(udtree.serialize()))
    original_sent_list = [x for x in udtree.serialize().split('\n') if x!= '']
    for word in original_sent_list:
        word = word.split('\t')[1]
        sent.append(word.replace(' ','_'))
    # ptbtree = ptbtree.copy(True)
    # ptbsent = ptbsent.copy()
    # removeemptynodes(ptbtree, ptbsent)
    # for subtree in ptbtree.subtrees():
    #     while subtree.label.endswith('-'):
    #         subtree.label = subtree.label[:-1]
    # print(' '.join(sent))
    # print()
    #udtree.print_tree()
    #print()
    #print(DrawTree(ptbtree, ptbsent))
    rrgtree = transform(udtree, language, layer='SENTENCE')
    # print(rrgtree)
    #  print()
    #print(DrawTree(rrgtree, ptbsent))
    #discodop_transform(rrgtree, sent, ('PTBbrackets', ))
    try:
        rrgtree_with_traces = add_traces_to_rrg(udtree, rrgtree, sent) # add traces from tanjas script
    except (AssertionError) as e  :
        # hiding this for now
        #logging.exception(e)
        return rrgtree,sent
    return rrgtree_with_traces, sent


if __name__ == '__main__':
    # Read gold corpus and create evaluator:
    print("Language? (en,de,hu,ru,fa)")
    compute_worst=False
    language=input()
    key_gold_map = {}
    for key, tree, sent, comment in export.read_file('gold_data/'+language+'_treebankGoldDev.export'):
        if tree.label == 'ROOT':
            assert len(tree) == 1
            tree = tree[0]
        key_gold_map[key] = (tree, sent, comment)
    params=readparam('evalparam.prm')
    evaluator = Evaluator(params)
    # Open PTB trees:
    #ptb_reader = NegraCorpusReader('treebankOriginalBracketing.export')
    # Open UD trees and convert:
    converted = 0
    failed = 0
    failed_set=set()
    with open('conllu/'+language+'.conllu') as ud_file, \
            open('ud2rrg_output/'+language+'_ConvertedFromUD.export', 'w') as rrg_file, \
                        open('ud2rrg_output/'+language+'_Input.export', 'w') as input_file:

        ud_reader = parse_tree_incr(ud_file)
        key=0
        prev_lp=Decimal(100.0)
        # sentence that caused the biggest drop in precision (drop,sentence_number)
        worst_drop=(0.0,-1)
        for ud_list in ud_reader:
            key+=1
            if str(key) not in key_gold_map:
                continue # for now, skip sentences we don't evaluate on
                #gold_tree, gold_sent=(None,None)
            # if key in (1513,2517,6205,3420,6148,5925,1514,1471,635,2781,2386,1831,1560,5924,414,
            #            # these ones are just "no!"
            #            5813,5818,5291,3419
            # ):
            #     continue
            else:
                gold_tree, gold_sent, _ = key_gold_map[str(key)]
            try:
                #print(key)
                rrg_tree, rrg_sent = ud2rrg(ud_list, language)
                if not gold_sent:
                    gold_sent=rrg_sent
                # to check the well-formedness of the tree
                DrawTree(rrg_tree,gold_sent)
                #print(DrawTree(rrg_tree,gold_sent))
                rrg_file.write(writeexporttree(ParentedTree('ROOT',[rrg_tree]), rrg_sent, key,
                                                                    None, morphology=None))
                canonicalize(rrg_tree)
                copy_function_tags(rrg_tree)
                if gold_tree:
                    # this is buggy at the moment
                    #if language=='fr' and key in (43,57,99,107,114,120,129,154,169,177,265,496,941,1159,2061,2542):
                    #    continue
                    if language=='fr' and key in (57,99,114,120,129,154,169,177,265,498,941,947,1167):
                        # the ones with wrong symbols for apostrophes (need to be updated, but are all silver)
                        continue
                    #if language=='fr' and key in (781,):
                        # the ones with very bad performance
                    #    continue
                    print(key)
                    assert gold_sent == rrg_sent
                    evaluator.add(key, gold_tree, gold_sent, rrg_tree, rrg_sent)
                    if compute_worst:
                        # this is the current precision
                        lp=Decimal(evaluator.acc.scores()['lp'])
                        drop=(lp-prev_lp)*Decimal(evaluator.acc.sentcount)
                        prev_lp=lp
                        if drop < worst_drop[0]:
                            worst_drop=(drop,key)
                converted += 1
            except (NotHandled,linkage.ClauseLinkageError,ValueError,AttributeError,IndexError,RecursionError) as e  :
                print(key)
                logging.exception(e)
                if gold_tree:
                    rrg_tree = ParentedTree('ROOT', list(p.copy(True) for p in util.preterminals(gold_tree)))
                    rrg_sent = gold_sent.copy()
                    evaluator.add(key, gold_tree, gold_sent, rrg_tree, rrg_sent)
                failed += 1
                failed_set.add(key)
    # Evaluate:
    evaluator.breakdowns()
    print(evaluator.summary())
    print('Sentences converted:', converted)
    print('Failed to convert:', failed)
    if failed_set:
        print('Failed set: ',sorted(failed_set))
    if compute_worst:
        print("Worst drop in precision: "+str(worst_drop[1])+" ("+str(worst_drop[0])+"%)")
