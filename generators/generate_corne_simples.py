#!/usr/bin/env python3
"""
Gerador canônico dedicado para o Corne Simples (7 camadas / 294 teclas).
Delega ao gerador consolidado com validação e cabeçalho de perfil simples.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_corne_candidato

def main():
    if "--profile" not in sys.argv:
        sys.argv.extend(["--profile", "simple"])
    generate_corne_candidato.main()

if __name__ == "__main__":
    main()
