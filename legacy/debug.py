from conllu import parse_tree_incr

with open('prueba.conllu') as f:
    for udtree in parse_tree_incr(f):
        print("Serializado:")
        print(repr(udtree.serialize()))
        break
