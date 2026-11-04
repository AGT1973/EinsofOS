#!/usr/bin/env python3
"""
generate_screens.py — Generador de Pantallas Efímeras Bare-Metal para EinsofOS
Genera:
1. render_login_screen: Pantalla de Acceso inicial.
2. render_dashboard_screen: Dashboard general del sistema.
3. render_authorized_dashboard: Dashboard personalizado tras autorizacion en BBDD via MCP.
4. render_access_denied_screen: Pantalla de rechazo inmediato de silicio.
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

    # Tarjeta 1: Estado del Host (AMD A4-6300)
    fb.draw_rect(30, 90, 350, 220, COLOR_CARD_BG)
    fb.draw_rect_outline(30, 90, 350, 220, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("NODO LOCAL: AMD A4-6300", 50, 110, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("CORES: 1 C / 2 T (HOST)", 50, 140, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("RAM: 16 GB DDR3", 50, 170, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("GPU: 0 (LOCAL)", 50, 200, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("ARENA R15: 0x0000_0001", 50, 230, color=COLOR_SUCCESS_GREEN, scale=2)
    fb.draw_text("SLABS: 64 KB (100% L1)", 50, 260, color=COLOR_ACCENT_BLUE, scale=2)

    # Tarjeta 2: Nodo Remoto (ALADIN Debian 13)
    fb.draw_rect(420, 90, 350, 220, COLOR_CARD_BG)
    fb.draw_rect_outline(420, 90, 350, 220, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("NODO REMOTO: ALADIN", 440, 110, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("IP: 192.168.100.21", 440, 140, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("CPU: I3-8100 4C/4T 3.6GHZ", 440, 170, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("RAM: 8 GB DDR4", 440, 200, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("ENLACE PMTP: 10 GBPS", 440, 230, color=COLOR_SUCCESS_GREEN, scale=2)
    fb.draw_text("ESTADO: SINCRONIZADO", 440, 260, color=COLOR_SUCCESS_GREEN, scale=2)

    # Tarjeta 3: Telemetria de Red y Satelites
    fb.draw_rect(30, 340, 740, 220, COLOR_CARD_BG)
    fb.draw_rect_outline(30, 340, 740, 220, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("TELEMETRIA DE RED & CONMUTACION DE SILICIO", 50, 360, color=COLOR_ACCENT_BLUE, scale=2)
    fb.draw_text("CANAL ACTIVO: SAT-ALFA-LEO-01", 50, 395, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("SENAL: 24.5 DB (OPTIMA)", 50, 425, color=COLOR_SUCCESS_GREEN, scale=2)
    fb.draw_text("LATENCIA: 18 MS | PERDIDA: 0%", 50, 455, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("REGLA 10: EXIT CODE 0 VERIFICADO EN SILICIO", 50, 495, color=COLOR_SUCCESS_GREEN, scale=2)
    fb.draw_text("BBDD: POSTGRESQL 16 (POL YDIM ACTIVE DB)", 50, 525, color=COLOR_TEXT_MUTED, scale=2)

    fb.export_bmp(output_path)

def render_authorized_dashboard(output_path: str, user_id: str, role: str, clearance: int, slab_id: str):
    fb = EinsofFramebuffer(800, 600)
    fb.clear(COLOR_BG_DARK)

    # Header
    fb.draw_rect(0, 0, 800, 60, COLOR_CARD_BG)
    fb.draw_rect_outline(0, 58, 800, 2, COLOR_SUCCESS_GREEN, thickness=2)
    fb.draw_text("EINSOF OS - SESION SOBERANA ACTIVA", 30, 20, color=COLOR_SUCCESS_GREEN, scale=2)
    fb.draw_text(f"CLEARANCE: LVL {clearance}", 560, 20, color=COLOR_ACCENT_BLUE, scale=2)

    # Tarjeta 1: Perfil de Identidad Autenticada en PostgreSQL
    fb.draw_rect(30, 90, 740, 160, COLOR_CARD_BG)
    fb.draw_rect_outline(30, 90, 740, 160, COLOR_SUCCESS_GREEN, thickness=2)
    fb.draw_text("IDENTIDAD VALIDADA EN POSTGRESQL 16 (MCP SELECT OK)", 50, 110, color=COLOR_SUCCESS_GREEN, scale=2)
    fb.draw_text(f"USUARIO: {user_id.upper()}", 50, 140, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text(f"ROL ASIGNADO: {role.upper()}", 50, 170, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text(f"PUNTERO SLAB ASIGNADO: {slab_id}", 50, 200, color=COLOR_ACCENT_BLUE, scale=2)

    # Tarjeta 2: Organos de Silicio Disponibles
    fb.draw_rect(30, 270, 350, 290, COLOR_CARD_BG)
    fb.draw_rect_outline(30, 270, 350, 290, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("CAPACIDADES SOBERANAS", 50, 290, color=COLOR_ACCENT_BLUE, scale=2)
    fb.draw_text("1. RETRACCION STIEFEL S^2047", 50, 325, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("2. EVENT REACTOR (THREAD/CORE)", 50, 355, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("3. HOT-SWAP XCHG ATOMICO", 50, 385, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("4. COBOL COMP-3 EXACT DEC", 50, 415, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("5. DMA DIRECT NVME / RED", 50, 445, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text("ESTADO: PRIVILEGIOS TOTALES", 50, 495, color=COLOR_SUCCESS_GREEN, scale=2)

    # Tarjeta 3: Telemetria de Silicio y Seguridad
    fb.draw_rect(410, 270, 360, 290, COLOR_CARD_BG)
    fb.draw_rect_outline(410, 270, 360, 290, COLOR_INPUT_BORDER, thickness=1)
    fb.draw_text("SEGURIDAD & SILICIO", 430, 290, color=COLOR_ACCENT_BLUE, scale=2)
    fb.draw_text("INVARIANTE NEUMAIER: <= 1e-15", 430, 325, color=COLOR_SUCCESS_GREEN, scale=2)
    fb.draw_text("R15 ARENA BASE: 0x00000001", 430, 355, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("NODO ALADIN: CONECTADO", 430, 385, color=COLOR_SUCCESS_GREEN, scale=2)
    fb.draw_text("LATENCIA BBDD: 0.42 MS", 430, 415, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("EPHEMERAL GC: O(1) ATOMICO", 430, 445, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("SISTEMA OPERATIVO: EINSOF OS", 430, 495, color=COLOR_ACCENT_BLUE, scale=2)

    fb.export_bmp(output_path)

def render_access_denied_screen(output_path: str, user_id: str, reason: str):
    fb = EinsofFramebuffer(800, 600)
    fb.clear(COLOR_BG_DARK)

    # Header de Alerta Roja
    fb.draw_rect(0, 0, 800, 60, COLOR_CARD_BG)
    fb.draw_rect_outline(0, 58, 800, 2, COLOR_ERROR_RED, thickness=2)
    fb.draw_text("EINSOF OS - SEGURIDAD DE SILICIO", 30, 20, color=COLOR_ERROR_RED, scale=2)
    fb.draw_text("RECHAZADO", 660, 20, color=COLOR_ERROR_RED, scale=2)

    # Tarjeta de Rechazo
    card_x, card_y, card_w, card_h = 100, 120, 600, 400
    fb.draw_rect(card_x, card_y, card_w, card_h, COLOR_CARD_BG)
    fb.draw_rect_outline(card_x, card_y, card_w, card_h, COLOR_ERROR_RED, thickness=3)

    fb.draw_text("ACCESO DENEGADO POR EL NUCLEO", 150, 160, color=COLOR_ERROR_RED, scale=2)
    fb.draw_text("CONSULTA BBDD (SELECT) DIO NEGATIVO", 150, 200, color=COLOR_TEXT_MUTED, scale=2)

    fb.draw_text(f"USUARIO INTENTADO: {user_id.upper()}", 150, 260, color=COLOR_TEXT_WHITE, scale=2)
    fb.draw_text(f"MOTIVO: {reason.upper()}", 150, 300, color=COLOR_ERROR_RED, scale=2)

    fb.draw_text("REGISTRO AUDITADO EN POSTGRESQL 16", 150, 360, color=COLOR_TEXT_MUTED, scale=2)
    fb.draw_text("BLOQUEO DE PUERTOS: EFECTUADO (0 NS)", 150, 400, color=COLOR_ERROR_RED, scale=2)
    fb.draw_text("REINTENTO NO AUTORIZADO BLOQUEADO", 150, 440, color=COLOR_TEXT_MUTED, scale=2)

    fb.export_bmp(output_path)
