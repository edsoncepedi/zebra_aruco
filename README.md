# zebra_aruco

Imprime marcadores ArUco (dicionario `DICT_4X4_50`, IDs 0 a 49) na impressora Zebra pela rede.
Etiqueta padrao: 50 x 30 mm, 203 dpi.

## Instalacao (uma vez)

No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Imprimir

```powershell
.\.venv\Scripts\python impressao.py --id 7 --host 172.16.8.5
```

- `--id` - numero do marcador (0 a 49)
- `--host` - IP da Zebra (`172.16.8.5`). A porta padrao e 6101; para outra, use `--port`.

O PC precisa estar na mesma rede da impressora.

Outros exemplos:

```powershell
# Varios IDs, uma etiqueta para cada
.\.venv\Scripts\python impressao.py --ids 10,11,12,13 --host 172.16.8.5

# 3 copias do ID 7
.\.venv\Scripts\python impressao.py --id 7 --copies 3 --host 172.16.8.5
```

## Se sair torto

Imprima a etiqueta de teste (moldura na borda e cruz no centro):

```powershell
.\.venv\Scripts\python impressao.py --teste --host 172.16.8.5
```

Se a moldura sair deslocada, corrija com `--offset-x-mm` e `--offset-y-mm` (negativo sobe).

Todas as opcoes: `.\.venv\Scripts\python impressao.py --help`
