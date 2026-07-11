PY := PYTHONPATH=src python3

.PHONY: fetch dados motor all trava distribuicao figures manuscript test verify fontes

fetch:            ## baixa/atualiza dados brutos (rede; fontes públicas, sem credencial)
	$(PY) -m aferir.fetch.rfb_federal
	$(PY) -m aferir.fetch.ibge
	$(PY) -m aferir.fetch.sidra_ipca
	$(PY) -m aferir.fetch.tru
	$(PY) -m aferir.fetch.anp
	$(PY) -m aferir.fetch.anp_precos
	$(PY) -m aferir.fetch.pof
	$(PY) -m aferir.fetch.siconfi_uniao
	$(PY) -m aferir.fetch.siconfi_estadual
	$(PY) -m aferir.fetch.siconfi_rreo
	$(PY) -m aferir.fetch.siconfi_municipal
	$(PY) -m aferir.fetch.siconfi_municipal_dca
	$(PY) -m aferir.fetch.planalto
	$(PY) -m aferir.fetch.ibge_porte
	$(PY) -m aferir.fetch.ibge_informalidade
	$(PY) -m aferir.fetch.bcb_sgs

dados:            ## camada de dados: brutos (data/raw) -> processados (data/processed)
	$(PY) -m aferir.inputs.seed
	$(PY) -m aferir.inputs.deducao_etanol
	$(PY) -m aferir.inputs.pof
	$(PY) -m aferir.inputs.pof legal
	$(PY) -m aferir.fetch.siconfi_municipal
	$(PY) -m aferir.inputs.gov_aquisicoes
	$(PY) -m aferir.inputs.uniao

motor:            ## motor tri-esfera: processados -> alíquotas/tabelas -> invariantes (gate)
	$(PY) -m aferir.classificacao
	$(PY) -m aferir.sifim_fbcf
	$(PY) -m aferir.is_ampliado
	$(PY) -m aferir.simples
	$(PY) -m aferir.pipeline
	$(PY) -m aferir.uncertainty --classificacao
	$(PY) -m aferir.trava
	$(PY) -m aferir.perfis_trava
	$(PY) -m aferir.robustez --vetores
	$(PY) -m aferir.cashback
	$(PY) -m aferir.distribuicao
	$(PY) -m aferir.tables
	$(PY) -m aferir.invariants

all: dados motor  ## pipeline determinístico completo: insumos -> alíquotas (gate bloqueante)

trava:            ## art. 475 §§10-11: λ* de encolhimento dos favorecimentos t.q. Σ = 26,5%
	$(PY) -m aferir.trava

distribuicao:     ## distribuição legal do IBS em 2033 (ADCT 131-132; LC 227 arts. 104-117)
	$(PY) -m aferir.distribuicao

figures:
	$(PY) -m aferir.figures

manuscript: all figures
	$(PY) -m aferir.manuscript

fontes:           ## macOS: extrai Helvetica Neue do sistema para assets/fonts (opcional; fallback DejaVu)
	python3 tools/extrai_fontes.py

test:
	$(PY) -m pytest tests/ -q -m "not network"

verify: all test  ## replicação completa
