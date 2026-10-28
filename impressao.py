#!/usr/bin/env python3
"""
Imprime marcador(es) ArUco numa impressora Zebra, a partir do ID, gerando ZPL nativo.

O marcador e desenhado com caixas ^GB (vetorial), entao sai nitido em qualquer DPI.

Exemplos:
    # So gerar o ZPL (para conferir em http://labelary.com/viewer.html)
    python impressao.py --id 7 --out marcador_7.zpl

    # Zebra em rede (porta RAW 6101)
    python impressao.py --id 7 --host 172.16.8.5

    # Zebra USB instalada no Windows (precisa de: pip install pywin32)
    python impressao.py --ids 10,11,12,13 --printer "ZDesigner ZD220-203dpi ZPL"

Cada ID vira uma etiqueta. Use --copies para repetir cada uma.
"""

import argparse
import socket
import sys

import cv2.aruco as aruco

MM_PER_INCH = 25.4


def mm_to_dots(mm: float, dpi: int) -> int:
    return round(mm / MM_PER_INCH * dpi)


def marker_bits(dictionary, marker_id: int) -> list:
    """Matriz de celulas do marcador (incluindo a borda preta): True = preto."""
    n = dictionary.markerSize + 2
    img = aruco.generateImageMarker(dictionary, marker_id, n)  # 1 pixel por celula
    return [[img[r, c] == 0 for c in range(n)] for r in range(n)]


def marker_zpl(dictionary, marker_id: int, args) -> tuple:
    """Retorna (ZPL da etiqueta, lado real do marcador em mm)."""
    bits = marker_bits(dictionary, marker_id)
    n = len(bits)
    label_w = mm_to_dots(args.label_width_mm, args.dpi)
    label_h = mm_to_dots(args.label_height_mm, args.dpi)

    # Etiqueta deitada: texto ao lado do marcador; em pe: texto embaixo
    side_text = args.text and label_w > label_h
    text_w = mm_to_dots(8, args.dpi) if side_text else 0
    text_h = mm_to_dots(3, args.dpi) if args.text and not side_text else 0

    # Modulo em pontos inteiros: evita celulas de tamanhos diferentes
    if args.size_mm is None:
        # Maior marcador que cabe deixando 1 modulo de margem branca (quiet zone) em volta
        module = min(label_w - 2 * text_w, label_h - text_h) // (n + 2)
    else:
        module = max(1, round(mm_to_dots(args.size_mm, args.dpi) / n))
    marker_dots = module * n
    x0 = (label_w - marker_dots) // 2  # marcador sempre centralizado
    y0 = (label_h - text_h - marker_dots) // 2

    if module < 1 or x0 < 0 or y0 < 0:
        sys.exit(f"[ERROR] Marcador de {args.size_mm}mm nao cabe na etiqueta "
                 f"{args.label_width_mm}x{args.label_height_mm}mm.")

    lines = label_header(label_w, label_h, args)
    for r, row in enumerate(bits):
        c = 0
        while c < n:
            if not row[c]:
                c += 1
                continue
            start = c
            while c < n and row[c]:
                c += 1
            # Junta celulas pretas consecutivas da linha numa unica caixa
            w = (c - start) * module
            lines.append(f"^FO{x0 + start * module},{y0 + r * module}^GB{w},{module},{min(w, module)},B^FS")

    if args.text:
        text = f"ID {marker_id}"
        font = mm_to_dots(2.5, args.dpi)
        if side_text:
            text_x = x0 + marker_dots
            lines.append(f"^FO{text_x},{(label_h - font) // 2}"
                         f"^FB{label_w - text_x},1,0,C^A0N,{font},{font}^FD{text}^FS")
        else:
            lines.append(f"^FO0,{y0 + marker_dots + mm_to_dots(0.5, args.dpi)}"
                         f"^FB{label_w},1,0,C^A0N,{font},{font}^FD{text}^FS")

    lines.append(f"^PQ{args.copies}")
    lines.append("^XZ")
    return "".join(lines), marker_dots / args.dpi * MM_PER_INCH


def label_header(label_w: int, label_h: int, args) -> list:
    dx = mm_to_dots(args.offset_x_mm, args.dpi)
    dy = mm_to_dots(args.offset_y_mm, args.dpi)
    lines = ["^XA", f"^PW{label_w}", f"^LL{label_h}"]
    # So envia ajuste de posicao quando pedido, para nao mexer na configuracao da impressora
    if dx:
        lines.append(f"^LH{max(dx, 0)},0")
    if dy:
        lines.append(f"^LT{dy}")  # ^LT aceita negativo (sobe a impressao)
    return lines


def test_zpl(args) -> str:
    """Etiqueta de calibracao: moldura na borda, cruz no centro e a configuracao escrita."""
    w = mm_to_dots(args.label_width_mm, args.dpi)
    h = mm_to_dots(args.label_height_mm, args.dpi)
    t = max(2, mm_to_dots(0.5, args.dpi))
    font = mm_to_dots(2.5, args.dpi)
    arm = mm_to_dots(5, args.dpi)
    lines = label_header(w, h, args) + [
        f"^FO0,0^GB{w},{h},{t},B^FS",
        f"^FO{w // 2 - arm},{h // 2}^GB{2 * arm},{t},{t},B^FS",
        f"^FO{w // 2},{h // 2 - arm}^GB{t},{2 * arm},{t},B^FS",
        f"^FO0,{mm_to_dots(2, args.dpi)}^FB{w},1,0,C^A0N,{font},{font}"
        f"^FD{args.label_width_mm:g}x{args.label_height_mm:g}mm {args.dpi}dpi^FS",
        "^PQ1",
        "^XZ",
    ]
    return "".join(lines)


def send_tcp(data: bytes, host: str, port: int):
    with socket.create_connection((host, port), timeout=10) as s:
        s.sendall(data)


def send_windows(data: bytes, printer: str):
    try:
        import win32print
    except ImportError:
        sys.exit("[ERROR] Para imprimir via fila do Windows instale: pip install pywin32")
    handle = win32print.OpenPrinter(printer)
    try:
        win32print.StartDocPrinter(handle, 1, ("ArUco ZPL", None, "RAW"))
        win32print.StartPagePrinter(handle)
        win32print.WritePrinter(handle, data)
        win32print.EndPagePrinter(handle)
        win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


def main():
    parser = argparse.ArgumentParser(description="Imprime marcadores ArUco numa Zebra (ZPL)")
    parser.add_argument("--dict", default="DICT_4X4_50", help="Dicionario ArUco (default: DICT_4X4_50)")
    parser.add_argument("--id", type=int, default=None, help="ID do marcador")
    parser.add_argument("--ids", default=None, help="Varios IDs separados por virgula (uma etiqueta por ID)")
    parser.add_argument("--size-mm", type=float, default=None,
                        help="Lado do marcador em mm (default: o maior que cabe na etiqueta)")
    parser.add_argument("--label-width-mm", type=float, default=50.0, help="Largura da etiqueta em mm (default: 50)")
    parser.add_argument("--label-height-mm", type=float, default=30.0, help="Altura da etiqueta em mm (default: 30)")
    parser.add_argument("--dpi", type=int, default=203, choices=[152, 203, 300, 600], help="Resolucao da Zebra (default: 203)")
    parser.add_argument("--copies", type=int, default=1, help="Copias de cada etiqueta (default: 1)")
    parser.add_argument("--no-text", dest="text", action="store_false", help="Nao imprimir 'ID n' abaixo do marcador")
    parser.add_argument("--offset-x-mm", type=float, default=0.0, help="Desloca a impressao para a direita, em mm")
    parser.add_argument("--offset-y-mm", type=float, default=0.0, help="Desloca a impressao para baixo (negativo = cima), em mm")
    parser.add_argument("--teste", action="store_true", help="Imprime etiqueta de calibracao (moldura + cruz central)")
    parser.add_argument("--host", help="IP da Zebra em rede (envia via porta RAW)")
    parser.add_argument("--port", type=int, default=6101)
    parser.add_argument("--printer", help="Nome da impressora instalada no Windows (envio RAW pelo spooler)")
    parser.add_argument("--out", help="Salvar o ZPL neste arquivo")
    args = parser.parse_args()

    if args.teste:
        ids, zpl = [], test_zpl(args)
    else:
        if args.ids:
            ids = [int(x) for x in args.ids.split(",")]
        elif args.id is not None:
            ids = [args.id]
        else:
            parser.error("informe --id, --ids ou --teste")

        dictionary = aruco.getPredefinedDictionary(getattr(aruco, args.dict))
        max_id = dictionary.bytesList.shape[0] - 1
        for mid in ids:
            if not 0 <= mid <= max_id:
                sys.exit(f"[ERROR] ID {mid} fora do dicionario {args.dict} (0 a {max_id}).")

        zpl, real_mm = "", 0.0
        for mid in ids:
            label, real_mm = marker_zpl(dictionary, mid, args)
            zpl += label
    data = zpl.encode("ascii")

    if args.out:
        with open(args.out, "w", encoding="ascii") as f:
            f.write(zpl)
        print(f"ZPL salvo em: {args.out}")
    if args.host:
        send_tcp(data, args.host, args.port)
        print(f"Enviado para {args.host}:{args.port}")
    if args.printer:
        send_windows(data, args.printer)
        print(f"Enviado para a impressora '{args.printer}'")
    if not (args.out or args.host or args.printer):
        sys.stdout.write(zpl)

    if ids:
        print(f"IDs: {ids}, dicionario {args.dict}, tamanho real do marcador: {real_mm:.2f}mm @ {args.dpi}dpi",
              file=sys.stderr)


if __name__ == "__main__":
    main()
