from __future__ import annotations

MAPEAMENTO: dict[str, tuple[str, str]] = {
    "TODOS OS INDICADORES": (
        "todos_indicadores",
        "interface_todos_indicadores",
    ),
    "CVLI": (
        "cvli",
        "interface_cvli",
    ),
    "CVP (SPORTAL)": (
        "cvp_sportal",
        "interface_cvp_sportal",
    ),
    "CVP (SIP)": (
        "cvp_sip",
        "interface_cvp_sip",
    ),
    "PERTURBAÇÃO AO SOSSEGO ALHEIO": (
        "perturbacao_sossego",
        "interface_perturbacao_sossego",
    ),
    "DESLOCAMENTO FORÇADO": (
        "deslocamento_forcado",
        "interface_deslocamento_forcado",
    ),
    "ROUBO DE VEÍCULO (SPORTAL)": (
        "roubo_veiculo_sportal",
        "interface_roubo_veiculo_sportal",
    ),
    "ROUBO DE VEÍCULO (SIP)": (
        "roubo_veiculo_sip",
        "interface_roubo_veiculo_sip",
    ),
    "ACIDENTE DE TRÂNSITO": (
        "acidente_transito",
        "interface_acidente_transito",
    ),
    "MORTES NO TRÂNSITO (SIP)": (
        "acidente_transito_sip",
        "interface_acidente_transito_sip",
    ),
    "FURTO DE VEÍCULO (SPORTAL)": (
        "furto_veiculo_sportal",
        "interface_furto_veiculo_sportal",
    ),
    "FURTO DE VEÍCULO (SIP)": (
        "furto_veiculo_sip",
        "interface_furto_veiculo_sip",
    ),
    "GEOCODIFICAÇÃO": (
        "geocodificar",
        "interface_geocodificar",
    ),
    "CONVERSÃO": (
        "conversor_coordenadas",
        "interface_conversor_coordenadas",
    ),
    "CONSOLIDAR INDICADORES": (
        "consolidar_indicadores_criminais",
        "interface_consolidar_indicadores_criminais",
    ),
}

INDICADORES_ATUALIZACAO: list[str] = [
    "CVLI",
    "CVP (SPORTAL)",
    "CVP (SIP)",
    "PERTURBAÇÃO AO SOSSEGO ALHEIO",
    "DESLOCAMENTO FORÇADO",
    "ROUBO DE VEÍCULO (SPORTAL)",
    "ROUBO DE VEÍCULO (SIP)",
    "ACIDENTE DE TRÂNSITO",
    "MORTES NO TRÂNSITO (SIP)",
    "FURTO DE VEÍCULO (SPORTAL)",
    "FURTO DE VEÍCULO (SIP)",
]

MODULOS_GEO: list[str] = [
    "GEOCODIFICAÇÃO",
    "CONVERSÃO",
]

MODULOS_CONSOLIDACAO: list[str] = [
    "CONSOLIDAR INDICADORES",
]
