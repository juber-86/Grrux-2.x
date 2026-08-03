import stanza

nlp = stanza.Pipeline('es', processors='tokenize,pos,lemma,depparse')

oraciones = [
    "la ventana está rota",
    "Juan es tonto",
    "Juan está en la biblioteca",
]

for oracion in oraciones:
    doc = nlp(oracion)
    sent = doc.sentences[0]
    print(f"\n── {oracion} ──")
    for w in sent.words:
        print(f"  id={w.id} texto={w.text:<12} lema={w.lemma:<12} "
              f"upos={w.upos:<6} deprel={w.deprel:<8} head={w.head}")
