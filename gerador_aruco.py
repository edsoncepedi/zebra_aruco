#!/usr/bin/env python3
"""
Gera marcador(es) ArUco para imprimir. Dois modos:

Modo unico (um marcador, uma folha):
    python generate_aruco_marker.py --id 0 --size-mm 30

Modo folha (varios marcadores numa unica pagina A4, ex: os 4 cantos da mesa):
    python generate_aruco_marker.py --ids 10,11,12,13 --size-mm 50 \\
        --labels "sup-esq,sup-dir,inf-dir,inf-esq" --out calibration/corners_sheet.pdf

Nao precisa de camera nem robo - roda local, uma vez.
"""

import argparse
import os
import sys

import cv2
import cv2.aruco as aruco
import numpy as np
from PIL import Image

DPI = 300
MM_PER_INCH = 25.4
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
LABEL_HEIGHT_MM = 10


def mm_to_px(mm: float) -> int:
    return round(mm / MM_PER_INCH * DPI)


def render_marker_cell(dictionary, marker_id: int, label: str, size_mm: float, border_mm: float) -> np.ndarray:
    """Renderiza um marcador + borda branca + rotulo de texto abaixo, como uma celula standalone."""
    marker_px = mm_to_px(size_mm)
    border_px = mm_to_px(border_mm)
    label_px = mm_to_px(LABEL_HEIGHT_MM)

    cell_w = marker_px + 2 * border_px
    cell_h = marker_px + 2 * border_px + label_px

    cell = np.full((cell_h, cell_w), 255, dtype=np.uint8)
    marker_img = aruco.generateImageMarker(dictionary, marker_id, marker_px)
    cell[border_px:border_px + marker_px, border_px:border_px + marker_px] = marker_img

    text = f"ID {marker_id}" + (f" - {label}" if label else "")
    cv2.putText(
        cell, text, (border_px, cell_h - border_px // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 0.03 * DPI / 10, 0, max(1, round(DPI / 150)),
    )
    return cell


def main():
    parser = argparse.ArgumentParser(description="Gera marcador(es) ArUco para imprimir")
    parser.add_argument("--dict", default="DICT_4X4_50", help="Nome do dicionario ArUco (default: DICT_4X4_50)")
    parser.add_argument("--id", type=int, default=0, help="ID do marcador (modo unico, default: 0)")
    parser.add_argument("--ids", default=None, help="Lista de IDs separados por virgula (modo folha, ex: 10,11,12,13)")
    parser.add_argument("--labels", default=None, help="Lista de rotulos separados por virgula, na mesma ordem de --ids")
    parser.add_argument("--cols", type=int, default=None, help="Colunas da grade no modo folha (default: automatico)")
    parser.add_argument("--size-mm", type=float, default=30.0, help="Tamanho de cada marcador impresso, em mm (default: 30)")
    parser.add_argument("--border-mm", type=float, default=10.0, help="Margem branca ao redor de cada marcador, em mm (default: 10)")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "aruco_marker.pdf"))
    args = parser.parse_args()

    dict_id = getattr(aruco, args.dict)
    dictionary = aruco.getPredefinedDictionary(dict_id)

    if args.ids is None:
        cell = render_marker_cell(dictionary, args.id, "", args.size_mm, args.border_mm)
        image = Image.fromarray(cell, mode="L")
        image.save(args.out, resolution=float(DPI))
        print(f"Salvo em: {args.out}")
        print(f"Dicionario: {args.dict}, ID: {args.id}, tamanho: {args.size_mm}mm")
        print("Imprima SEM ajuste de escala ('Tamanho real' / 100%) e recorte.")
        print(f"ID {args.id} no esquema deste projeto: 0=garra, 1=peca X, 2=peca O, 10-13=cantos da mesa.")
        return

    ids = [int(x) for x in args.ids.split(",")]
    labels = args.labels.split(",") if args.labels else [""] * len(ids)
    if len(labels) != len(ids):
        print("[ERROR] --labels precisa ter a mesma quantidade de itens que --ids", file=sys.stderr)
        sys.exit(1)

    cols = args.cols or int(np.ceil(np.sqrt(len(ids))))
    rows = int(np.ceil(len(ids) / cols))

    cells = [render_marker_cell(dictionary, mid, lbl, args.size_mm, args.border_mm) for mid, lbl in zip(ids, labels)]
    cell_h, cell_w = cells[0].shape

    grid_w_px = cols * cell_w
    grid_h_px = rows * cell_h
    page_w_px = mm_to_px(A4_WIDTH_MM)
    page_h_px = mm_to_px(A4_HEIGHT_MM)

    if grid_w_px > page_w_px or grid_h_px > page_h_px:
        print(
            f"[ERROR] {len(ids)} marcadores de {args.size_mm}mm numa grade {cols}x{rows} nao cabem em A4. "
            "Reduza --size-mm, aumente --cols ou gere menos marcadores por folha.",
            file=sys.stderr,
        )
        sys.exit(1)

    page = np.full((page_h_px, page_w_px), 255, dtype=np.uint8)
    off_x = (page_w_px - grid_w_px) // 2
    off_y = (page_h_px - grid_h_px) // 2
    for i, cell in enumerate(cells):
        r, c = divmod(i, cols)
        y0 = off_y + r * cell_h
        x0 = off_x + c * cell_w
        page[y0:y0 + cell_h, x0:x0 + cell_w] = cell

    image = Image.fromarray(page, mode="L")
    image.save(args.out, resolution=float(DPI))

    print(f"Salvo em: {args.out}")
    print(f"IDs: {ids}, tamanho: {args.size_mm}mm cada, grade {cols}x{rows}")
    print("Imprima SEM ajuste de escala ('Tamanho real' / 100%) e recorte cada marcador.")


if __name__ == "__main__":
    main()