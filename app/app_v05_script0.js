\n/* Referencias locais atualizadas")
    if idx_vils == -1:
        raise ValueError("Tag de referências VIL não encontrada no HTML original!")
    vil_and_after = orig_html[idx_vils:]

    html_head_and_body = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Keyboard Split Manager v05 Homologado • Corne & Sofle</title>
  <script src="https://cdn.tailwindcss.com">