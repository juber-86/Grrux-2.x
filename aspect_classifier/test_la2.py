"""Pruebas frías de los contratos nuevos de LA2."""

from .causatividad import componer_cause
from .gui_contract import NODE_GLOSSARY_KEYS, ROUTING_INVENTORY, inventario_enrutado
from . import display_grr, glosario, linking


def test_se_heuristico_resultativo_espanol_y_ls_estructura():
    ls = componer_cause("Activity", None, "vender", None, "casas", True,
                        causativo_heuristico=True)
    assert ls["formal"] == "[do'(Ø, Ø)] CAUSE [BECOME vendido'(y)]"
    assert ls["lexical"] == "[do'(Ø, Ø)] CAUSE [BECOME vendido'(casas)]"
    assert ls["estructura"][1]["args"][0]["posicion"] == "arg_estado"
    assert "sold'" not in ls["lexical"]


def test_causativa_puntual_conserva_ngr():
    ls = componer_cause("Achievement", "broken'", "romper", "Juan", "ventana", False)
    assert ls["lexical"] == "[do'(Juan, Ø)] CAUSE [INGR roto'(ventana)]"


def test_linking_se_venden_casas_es_undergoer_y_psa():
    ls = componer_cause("Activity", None, "vender", None, "casas", True,
                        causativo_heuristico=True)
    linking.enriquecer_ids(ls["estructura"], {"casas": 3})
    resultado = linking.analizar_linking(
        ls["estructura"],
        {"core": [{"id": 3, "text": "casas", "deprel": "nsubj",
                   "macropapel": "Undergoer"}], "periferia": [], "impersonal": False},
        [{"clitico": "se", "fuente": "se_pasivo", "clitico_id": 1}],
        {"se_anticausativo": True},
        [{"id": 1, "text": "Se", "lemma": "él", "upos": "PRON",
          "deprel": "expl:pass", "head": 2, "feats": ""},
         {"id": 2, "text": "venden", "lemma": "vender", "upos": "VERB",
          "deprel": "root", "head": 0,
          "feats": "Number=Plur|Person=3|VerbForm=Fin"},
         {"id": 3, "text": "casas", "lemma": "casa", "upos": "NOUN",
          "deprel": "nsubj", "head": 2, "feats": "Number=Plur|Person=3"}],
        2, "activity")
    assert resultado["macropapeles"]["actor"] is None
    assert resultado["macropapeles"]["undergoer"]["texto"] == "casas"
    assert resultado["psa"]["macrorol"] == "Undergoer"
    assert resultado["concordancia"]["ok"] is True


def test_linking_juan_rompio_la_ventana_es_causativa():
    ls = componer_cause("Achievement", "roto'", "romper", "Juan", "ventana", False)
    linking.enriquecer_ids(ls["estructura"], {"Juan": 1, "ventana": 4})
    resultado = linking.analizar_linking(
        ls["estructura"],
        {"core": [{"id": 1, "text": "Juan", "deprel": "nsubj", "macropapel": "Actor"},
                  {"id": 4, "text": "ventana", "deprel": "obj", "macropapel": "Undergoer"}],
         "periferia": [], "impersonal": False}, [], {"causativo": True},
        [{"id": 1, "text": "Juan", "lemma": "Juan", "upos": "PROPN",
          "deprel": "nsubj", "head": 2, "feats": "Number=Sing|Person=3"},
         {"id": 2, "text": "rompió", "lemma": "romper", "upos": "VERB",
          "deprel": "root", "head": 0,
          "feats": "Number=Sing|Person=3|VerbForm=Fin"},
         {"id": 4, "text": "ventana", "lemma": "ventana", "upos": "NOUN",
          "deprel": "obj", "head": 2, "feats": "Number=Sing|Person=3"}],
        2, "achievement")
    assert resultado["macropapeles"]["actor"]["texto"] == "Juan"
    assert resultado["macropapeles"]["undergoer"]["texto"] == "ventana"
    assert resultado["psa"]["macrorol"] == "Actor"


def test_terminal_muestra_clase_causal_y_linking():
    ls = {
        "ls_type": "achievement",
        "causativo": True,
        "causativo_clase_derivada": "logro_causativo",
        "causativo_tipo": "lexico_transitivo",
        "causativo_source": "lexicon",
        "causativo_confianza": "alta",
        "ls_formal": "[do'(x, Ø)] CAUSE [INGR roto'(y)]",
        "ls_lexical": "[do'(Juan, Ø)] CAUSE [INGR roto'(ventana)]",
        "linking": {
            "macropapeles": {
                "actor": {"texto": "Juan", "justificacion": "1er arg. de do'"},
                "undergoer": {"texto": "ventana", "justificacion": "arg. de estado roto'"},
                "nmr": [], "m_transitividad": 2,
            },
            "psa": {"macrorol": "Actor"},
            "concordancia": {"corto": "3sg", "ok": True},
        },
    }
    texto = display_grr.render_bloque(ls, arbol_texto=None)
    assert "Tipo       : Logro causativo" in texto
    assert "Linking: Actor=Juan" in texto


def test_mapa_tooltips_exactos_n_v_p_y_cobertura():
    entradas = glosario.cargar_glosario()
    por_termino = {e["termino"]: e["definicion"] for e in entradas}
    assert por_termino[NODE_GLOSSARY_KEYS["N"]].startswith("Categoría léxica nominal")
    assert por_termino[NODE_GLOSSARY_KEYS["V"]].startswith("Categoría léxica verbal")
    assert por_termino[NODE_GLOSSARY_KEYS["P"]].startswith("Categoría léxica que")
    assert all(key and value in por_termino for key, value in NODE_GLOSSARY_KEYS.items())


def test_inventario_enrutado_completo_y_ausentes():
    inv = inventario_enrutado({"root_id": 2, "verb_lemma": "vender",
                               "core": [], "periferia": [], "agx": []})
    assert [r["clave"] for r in inv] == [r["clave"] for r in ROUTING_INVENTORY]
    assert all(r["ausente"] for r in inv if r["clave"] != "nuc_predicado")
    assert any(r["clave"] == "prcs" and r["automatizacion"] == "solo_staging" for r in inv)
