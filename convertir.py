import sys
import traceback
from conllu import parse_tree_incr
import ud2rrg as converter
from discodop.tree import DrawTree
 
input_file = sys.argv[1] if len(sys.argv) > 1 else 'prueba.conllu'
language = sys.argv[2] if len(sys.argv) > 2 else 'en'
 
print(f"Convirtiendo: {input_file} (idioma: {language})\n")
 
converted = 0
failed = 0
 
with open(input_file) as f:
    for udtree in parse_tree_incr(f):
        try:
            sent = []
            original_sent_list = [x for x in udtree.serialize().split('\n')
                                  if x != '' and not x.startswith('#') and '\t' in x]
            for word in original_sent_list:
                w = word.split('\t')[1]
                sent.append(w.replace(' ', '_'))
 
            rrgtree = converter.transform(udtree, language, layer='SENTENCE')
            try:
                rrgtree_final = converter.add_traces_to_rrg(udtree, rrgtree, sent)
            except AssertionError:
                rrgtree_final = rrgtree
 
            print(f"--- Oración {converted+1} ---")
            print(' '.join(sent))
            print(DrawTree(rrgtree_final, sent))
            print()
            converted += 1
        except Exception as e:
            print(f"ERROR en oración {converted+failed+1}: {e}")
            traceback.print_exc()
            failed += 1
 
print(f"Convertidas: {converted} | Fallidas: {failed}")



