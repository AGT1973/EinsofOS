#!/usr/bin/env python3
"""
generate_screens.py — Generador de Pantallas Efímeras Bare-Metal para EinsofOS
Genera:
1. pantalla1_login.bmp: Pantalla de Acceso (Usuario, Password, Boton Ingresar)
2. pantalla2_dashboard.bmp: Pantalla del Servidor (Metricas de Racks, Memoria, Nodos, Red)
"""

import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(base_dir, "src"))

from einsof_display import (
    EinsofFramebuffer, COLOR_BG_DARK, COLOR_CARD_BG, COLOR_TEXT_WHITE,
    COLOR_TEXT_MUTED, COLOR_ACCENT_BLUE, COLOR_SUCCESS_GREEN, COLOR_ERROR_RED,
    COLOR_INPUT_BORDER, COLOR_INPUT_BG
)

def render_login_screen(output_path: str):
    fb = EinsofFramebuffer(800, 600)
    fb.clear(COLOR_BG_DARK)

    # Tarjeta Central de Login
    card_x, card_y, card_w, card_h = 200, 120, 400, 360
    fb.draw_rect(card_x, card_y, card_w, card_h, COLOR_CARD_BG)
    fb.draw_rect_outline(card_x, card_y, card_w, card_h, COLOR_ACCENT_BLUE, thickness=2)

    # Titulo
    fb.draw_text("EINSOF OS", 320, 150, color=COLOR_ACCENT_BLUE, scale=3)
    fb.draw_text("ACCESO AL SERVIDOR", 280, 200, color=COLOR_TEXT_MUTED, scale=2)

    # Campo Usuario
    fb.draw_text("USUARIO:", 230, 250, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_rect(230, 275, 340, 35, COLOR_INPUT_BG)
    fb.draw_rect_outline(230, 275, 340, 35, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("ARIEL", 240, 285, color=COLOR_TEXT_WHITE, scale=2)

    # Campo Password
    fb.draw_text("PASSWORD:", 230, 325, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_rect(230, 350, 340, 35, COLOR_INPUT_BG)
    fb.draw_rect_outline(230, 350, 340, 35, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("********", 240, 360, color=COLOR_ACCENT_BLUE, scale=2)

    # Boton Ingresar
    fb.draw_rect(230, 410, 340, 45, COLOR_ACCENT_BLUE)
    fb.draw_text("INGRESAR", 330, 422, color=COLOR_BG_DARK, scale=2)

    fb.export_bmp(output_path)

def render_dashboard_screen(output_path: str):
    fb = EinsofFramebuffer(800, 600)
    fb.clear(COLOR_BG_DARK)

    # Barra Superior (Header)
    fb.draw_rect(0, 0, 800, 60, COLOR_CARD_BG)
    fb.draw_rect_outline(0, 58, 800, 2, COLOR_ACCENT_BLUE, thickness=2)
    fb.draw_text("EINSOF OS - PANEL DE CONTROL CENTRAL", 30, 20, color=COLOR_ACCENT_BLUE, scale=2)
    fb.draw_text("ONLINE", 700, 20, color=COLOR_SUCCESS_GREEN, scale=2)

    # Tarjeta 1: Estado del Servidor
    fb.draw_rect(30, 90, 350, 220, COLOR_CARD_BG)
    fb.draw_rect_outline(30, 90, 350, 220, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("INFRAESTRUCTURA Y HARDWARE", 50, 110, color=COLOR_ACCENT_BLUE, scale=2)
    fb.draw_text("NODO: ALADIN (DEBIAN 13)", 50, 150, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("CPU: INTEL CORE I3-8100 4C", 50, 180, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("INSTRUCCIONES: AVX2 / FMA", 50, 210, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("ESTADO SILICIO: EXIT CODE 0", 50, 250, color=COLOR_SUCCESS_GREEN, scale=2)

    # Tarjeta 2: Memoria y Almacenamiento
    fb.draw_rect(410, 90, 360, 220, COLOR_CARD_BG)
    fb.draw_rect_outline(410, 90, 360, 220, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("MEMORIA ARENA Y RACKS", 430, 110, color=COLOR_ACCENT_BLUE, scale=2)
    fb.draw_text("BASE MAESTRA: REGISTRO R15", 430, 150, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("CAPACIDAD ARENA: 64 MB ACTIVA", 430, 180, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("ALINEACION SLABS: 64 BYTES", 430, 210, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("PRECISION COBOL: ZERO-DRIFT", 430, 250, color=COLOR_SUCCESS_GREEN, scale=2)

    # Tarjeta 3: Telemetria de Red y Slaves
    fb.draw_rect(30, 340, 740, 220, COLOR_CARD_BG)
    fb.draw_rect_outline(30, 340, 740, 220, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("TELEMETRIA DE SERVIDOR Y USUARIOS", 50, 360, color=COLOR_ACCENT_BLUE, scale=2)
    fb.draw_text("USUARIO ACTIVO: ARIEL GARCIA TRABA (ADMIN)", 50, 400, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("SALDO EXACTO COBOL: 14877.0500 USD", 50, 430, color=COLOR_SUCCESS_GREEN, scale=2)
    fb.draw_text("AFINIDAD STIEFEL: 1.000000000000000", 50, 460, color=COLOR_ACCENT_BLUE, scale=2)
    fb.draw_text("PANTALLA 1: DESTRUIDA EN O(1) POR INVALIDACION GENERACIONAL", 50, 500, color=COLOR_TEXT_MUTED, scale=2)

    fb.export_bmp(output_path)

if __name__ == "__main__":
    screens_dir = os.path.join(base_dir, "screens")
    os.makedirs(screens_dir, exist_ok=True)
    p1 = os.path.join(screens_dir, "pantalla1_login.bmp")
    p2 = os.path.join(screens_dir, "pantalla2_dashboard.bmp")

    render_login_screen(p1)
    render_dashboard_screen(p2)
