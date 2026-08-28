/* Contrato visual LA2.1: confianza válida = número finito entre 0 y 1. */
"use strict";

(function exponerContratoConfianza(global) {
  function confianzaNumerica(valor) {
    if (valor === null || valor === undefined || typeof valor === "boolean") return null;
    if (typeof valor === "string" && valor.trim() === "") return null;
    const numero = Number(valor);
    return Number.isFinite(numero) && numero >= 0 && numero <= 1 ? numero : null;
  }

  function formatearConfianza(valor) {
    const numero = confianzaNumerica(valor);
    return numero == null ? "—" : numero.toFixed(2);
  }

  global.GrruxConfianza = { confianzaNumerica, formatearConfianza };
})(globalThis);
