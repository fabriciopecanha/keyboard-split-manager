#!/usr/bin/env python3
"""generate_sofle_candidato — WRAPPER LEGADO (redireciona para compose_sofle_candidato.py).

AVISO DE DEPRECATED:
Este script é o caminho legado de geração do Sofle.
O gerador oficial e calibrado é: ksm-work/generators/compose_sofle_candidato.py
que implementa a inversão física da metade direita (.vil[r+5][c] = matrix[r][11-c]),
inversão dos dedões direitos (.vil[9][c] = thumbs[9-c]), tradução determinística de macros
M1..M10 e validação estrita contra o repositório QMK e o homologado.

Para evitar duplicação ou divergência, este script atua como um wrapper explícito,
repassando a execução para compose_sofle_candidato.py.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OFFICIAL_COMPOSER = os.path.join(HERE, "compose_sofle_candidato.py")

def main():
    print("AVISO: ksm-work/generators/generate_sofle_candidato.py é legado.", file=sys.stderr)
    print("Redirecionando para o gerador oficial: compose_sofle_candidato.py\n", file=sys.stderr)

    ap = argparse.ArgumentParser(description="Wrapper legado para compose_sofle_candidato.py")
    ap.add_argument("--dataset", default=os.path.join(HERE, "..", "data", "keymap_data_v06.json"))
    ap.add_argument("--base", default=None, help="Base .vil (ignorado; o oficial usa SOFLE_FINAL_HOMOLOGADO_v01.vil)")
    ap.add_argument("--out", default=None, help="Arquivo .vil de destino")
    ap.add_argument("--outdir", default=None, help="Diretório de saída para os candidatos")
    ap.add_argument("--apply-candidate-layer", action="append", default=[],
                    help="Camadas a aplicar (ignorado; o oficial compõe segundo a política de candidatos)")
    args = ap.parse_args()

    cmd = [sys.executable, OFFICIAL_COMPOSER, "--dataset", os.path.abspath(args.dataset)]
    if args.outdir:
        cmd.extend(["--outdir", os.path.abspath(args.outdir)])
    elif args.out:
        cmd.extend(["--out", os.path.abspath(args.out)])
    else:
        candidates_dir = os.path.join(HERE, "candidates", "sofle_v06")
        cmd.extend(["--outdir", candidates_dir])

    res = subprocess.run(cmd)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
