"""Regresiones frías de la auditoría de logros canónicos LA2.1."""

from rrg_ls_mapper import debe_degradar_por_objeto_desnudo
from .causatividad import componer_cause


def test_explotar_logro_lexico_no_degrada_por_objeto_desnudo():
    assert not debe_degradar_por_objeto_desnudo(
        "achievement", sujeto_agentivo=True, obj_delimita=False,
        clase_lexica="achievement")


def test_actividad_lexica_mal_predicha_si_puede_degradar():
    assert debe_degradar_por_objeto_desnudo(
        "achievement", sujeto_agentivo=True, obj_delimita=False,
        clase_lexica="activity")


def test_romper_causativa_lexica_usa_ingr_y_participio_espanol():
    ls = componer_cause("Achievement", "broken'", "romper",
                        "Juan", "ventana", False)
    assert ls["lexical"] == "[do'(Juan, Ø)] CAUSE [INGR roto'(ventana)]"
    assert ls["estructura"][0]["args"][0]["posicion"] == "1_do"
    assert ls["estructura"][1]["args"][0]["posicion"] == "arg_estado"
