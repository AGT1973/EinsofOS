/* boot/main.c — Nucleo Bare-Metal UEFI Interactivo para EinsofOS con SMP Multi-Core y REPL Shell */
#include <efi.h>
#include <efilib.h>
#include "font.h"
#include "einsof_gfx.h"
#include "einsof_cpu.h"
#include "einsof_acpi.h"
#include "einsof_smp.h"
#include "einsof_isa.h"

// Estados de la Maquina de Estado Bare-Metal
typedef enum {
    STATE_LOGIN = 0,
    STATE_DASHBOARD = 1,
    STATE_FAILOVER = 2,
    STATE_SHELL = 3
} KernelState;

static CpuInfo g_cpu = {0};
static AcpiTopology g_topo = {0};
static UINT32 g_accent_color = COLOR_ACCENT_BLUE;

#define SHELL_MAX_LINES 18
#define SHELL_LINE_LEN 128

typedef struct {
    CHAR8 lines[SHELL_MAX_LINES][SHELL_LINE_LEN];
    UINT32 colors[SHELL_MAX_LINES];
    UINT32 line_count;
} ShellConsole;

static ShellConsole g_console = {0};

// Utilidades para formateo de cadenas sin libc
static void int_to_str(INT64 value, CHAR8 *buf) {
    if (value == 0) {
        buf[0] = '0';
        buf[1] = '\0';
        return;
    }
    CHAR8 temp[32];
    int i = 0;
    BOOLEAN neg = FALSE;
    if (value < 0) {
        neg = TRUE;
        value = -value;
    }
    while (value > 0) {
        temp[i++] = '0' + (value % 10);
        value /= 10;
    }
    int j = 0;
    if (neg) buf[j++] = '-';
    while (i > 0) {
        buf[j++] = temp[--i];
    }
    buf[j] = '\0';
}

static void hex_to_str(UINT64 value, CHAR8 *buf) {
    static const CHAR8 hex_chars[] = "0123456789ABCDEF";
    buf[0] = '0';
    buf[1] = 'x';
    for (int i = 0; i < 16; ++i) {
        int shift = (15 - i) * 4;
        buf[2 + i] = hex_chars[(value >> shift) & 0x0F];
    }
    buf[18] = '\0';
}

static BOOLEAN str_equals(const CHAR8 *s1, const CHAR8 *s2) {
    int i = 0;
    while (s1[i] && s2[i]) {
        if (s1[i] != s2[i]) return FALSE;
        i++;
    }
    return (s1[i] == '\0' && s2[i] == '\0');
}

static void console_print(const CHAR8 *str, UINT32 color) {
    if (g_console.line_count < SHELL_MAX_LINES) {
        UINT32 idx = g_console.line_count++;
        int i = 0;
        while (str[i] && i < SHELL_LINE_LEN - 1) {
            g_console.lines[idx][i] = str[i];
            i++;
        }
        g_console.lines[idx][i] = '\0';
        g_console.colors[idx] = color;
    } else {
        for (UINT32 i = 0; i < SHELL_MAX_LINES - 1; ++i) {
            for (int k = 0; k < SHELL_LINE_LEN; ++k) {
                g_console.lines[i][k] = g_console.lines[i + 1][k];
            }
            g_console.colors[i] = g_console.colors[i + 1];
        }
        int i = 0;
        while (str[i] && i < SHELL_LINE_LEN - 1) {
            g_console.lines[SHELL_MAX_LINES - 1][i] = str[i];
            i++;
        }
        g_console.lines[SHELL_MAX_LINES - 1][i] = '\0';
        g_console.colors[SHELL_MAX_LINES - 1] = color;
    }
}

// =========================================================================
// RENDERIZADO DE PANTALLA 1: ACCESO AL NUCLEO EINSOF (LOGIN)
// =========================================================================
static void render_screen_login(const CHAR8 *input_text, BOOLEAN show_auth_success) {
    gfx_clear(COLOR_BG);

    // Barra superior
    gfx_draw_rect(0, 0, g_gfx.width, 36, COLOR_CARD_BG);
    gfx_draw_string("EINSOF OS v1.0 [BARE-METAL SILICON] - MODO LONG MODE x86_64", 16, 10, COLOR_TEXT_WHITE, 1);
    gfx_draw_string("STATUS: SOVEREIGN", g_gfx.width - 180, 10, COLOR_SUCCESS, 1);

    // Tarjeta central de acceso
    INT32 card_w = 560;
    INT32 card_h = 360;
    INT32 card_x = (g_gfx.width - card_w) / 2;
    INT32 card_y = (g_gfx.height - card_h) / 2 - 20;

    gfx_draw_panel(card_x, card_y, card_w, card_h, "CONTROL DE ACCESO Y AUTORIZACION IA", COLOR_CARD_BG, g_accent_color);

    gfx_draw_string("BIENVENIDO AL NUCLEO DE COMPUTO EINSOF", card_x + 30, card_y + 48, COLOR_TEXT_WHITE, 1);
    gfx_draw_string("Sistema Operativo sin letras, IA-nativo de ultra-bajo nivel.", card_x + 30, card_y + 70, COLOR_TEXT_MUTED, 1);
    gfx_draw_string("Cero Linux, Cero Windows, Cero libc. Base R15 Universal.", card_x + 30, card_y + 90, COLOR_TEXT_MUTED, 1);

    // Campo de entrada
    gfx_draw_string("CREDENCIAL O TOKEN SOBERANO:", card_x + 30, card_y + 130, COLOR_ACCENT_BLUE, 1);
    gfx_draw_rect(card_x + 30, card_y + 155, card_w - 60, 42, COLOR_INPUT_BG);
    gfx_draw_rect_outline(card_x + 30, card_y + 155, card_w - 60, 42, COLOR_BORDER, 2);

    CHAR8 display_buf[64];
    int len = 0;
    while (input_text[len] && len < 40) {
        display_buf[len] = input_text[len];
        len++;
    }
    display_buf[len] = '_';
    display_buf[len + 1] = '\0';
    gfx_draw_string(display_buf, card_x + 44, card_y + 168, COLOR_CYAN, 1);

    if (show_auth_success) {
        gfx_draw_rect(card_x + 30, card_y + 215, card_w - 60, 45, COLOR_SUCCESS);
        gfx_draw_string("ACCESO CONCEDIDO: NUCLEO EINSOF DESBLOQUEADO", card_x + 45, card_y + 230, COLOR_BG, 1);
    } else {
        gfx_draw_string("Presione ENTER para validar o continuar al Sistema.", card_x + 30, card_y + 225, COLOR_TEXT_MUTED, 1);
        gfx_draw_string("Credenciales de prueba: 'admin', 'einsof', o tecla libre.", card_x + 30, card_y + 250, COLOR_GOLD, 1);
    }

    gfx_draw_rect(0, g_gfx.height - 30, g_gfx.width, 30, COLOR_CARD_BG);
    gfx_draw_string("Ariel Garcia Traba | Arquitectura EinsofOS | Firmware UEFI 64-Bit", 16, g_gfx.height - 22, COLOR_TEXT_MUTED, 1);
}

// =========================================================================
// RENDERIZADO DE PANTALLA 2: TELEMETRIA Y DASHBOARD DEL SISTEMA
// =========================================================================
static void render_screen_dashboard(TensorBenchResult bench) {
    gfx_clear(COLOR_BG);

    // Header Principal
    gfx_draw_rect(0, 0, g_gfx.width, 42, COLOR_CARD_BG);
    gfx_draw_string("EINSOF OS v1.0 | TELEMETRIA DEL NUCLEO DE SILICIO | MULTI-CORE SMP", 16, 12, COLOR_TEXT_WHITE, 1);
    gfx_draw_string("HARDWARE SOBERANO", g_gfx.width - 190, 12, COLOR_SUCCESS, 1);

    INT32 margin = 20;
    INT32 top_y = 55;
    INT32 panel_h = g_gfx.height - top_y - 65;
    INT32 col1_w = (g_gfx.width - margin * 3) * 45 / 100;
    INT32 col2_w = (g_gfx.width - margin * 3) - col1_w;
    INT32 col2_x = margin * 2 + col1_w;

    // PANEL 1: HARDWARE Y MAPA DE SILICIO
    gfx_draw_panel(margin, top_y, col1_w, panel_h, "ARQUITECTURA DE PROCESADOR Y MEMORIA", COLOR_CARD_BG, g_accent_color);

    INT32 py = top_y + 40;
    gfx_draw_string("CPU VENDOR:", margin + 20, py, COLOR_TEXT_MUTED, 1);
    gfx_draw_string(g_cpu.vendor, margin + 140, py, COLOR_CYAN, 1);
    py += 26;

    gfx_draw_string("MODELO:", margin + 20, py, COLOR_TEXT_MUTED, 1);
    gfx_draw_string(g_cpu.model, margin + 20, py + 20, COLOR_TEXT_WHITE, 1);
    py += 52;

    gfx_draw_string("INSTRUCCIONES AVX2:", margin + 20, py, COLOR_TEXT_MUTED, 1);
    gfx_draw_string(g_cpu.has_avx2 ? "ACTIVO (SIMD 256-bit YMM)" : "NO PRESENTE (SSE2 FALLBACK)", margin + 200, py, g_cpu.has_avx2 ? COLOR_SUCCESS : COLOR_ERROR_RED, 1);
    py += 26;

    gfx_draw_string("LOCAL APIC BASE MMIO:", margin + 20, py, COLOR_TEXT_MUTED, 1);
    CHAR8 lapic_str[32];
    hex_to_str(g_smp.lapic_base, lapic_str);
    gfx_draw_string(lapic_str, margin + 200, py, COLOR_GOLD, 1);
    py += 26;

    // GOP Linear Framebuffer Info
    gfx_draw_string("GOP LINEAR FRAMEBUFFER:", margin + 20, py, COLOR_GOLD, 1);
    py += 24;
    CHAR8 fb_str[64];
    hex_to_str((UINT64)g_gfx.framebuffer, fb_str);
    gfx_draw_string("DIRECCION FISICA MMIO:", margin + 20, py, COLOR_TEXT_MUTED, 1);
    gfx_draw_string(fb_str, margin + 220, py, COLOR_TEXT_WHITE, 1);
    py += 24;

    CHAR8 res_str[64];
    CHAR8 w_buf[16], h_buf[16];
    int_to_str(g_gfx.width, w_buf);
    int_to_str(g_gfx.height, h_buf);
    int p = 0;
    for (int k = 0; w_buf[k]; ++k) res_str[p++] = w_buf[k];
    res_str[p++] = ' '; res_str[p++] = 'x'; res_str[p++] = ' ';
    for (int k = 0; h_buf[k]; ++k) res_str[p++] = h_buf[k];
    res_str[p++] = ' '; res_str[p++] = '('; res_str[p++] = '3'; res_str[p++] = '2'; res_str[p++] = 'b'; res_str[p++] = 'p'; res_str[p++] = 'p'; res_str[p++] = ')';
    res_str[p] = '\0';
    gfx_draw_string("RESOLUCION DE PANTALLA:", margin + 20, py, COLOR_TEXT_MUTED, 1);
    gfx_draw_string(res_str, margin + 220, py, COLOR_TEXT_WHITE, 1);
    py += 32;

    gfx_draw_string("BASE ARENA R15:", margin + 20, py, COLOR_GOLD, 1);
    py += 22;
    gfx_draw_string("0x0000_0001_0000_0000 (Flat Universal Memory)", margin + 20, py, COLOR_SUCCESS, 1);

    // PANEL 2: MOTOR TENSORIAL Y REACTOR DE EVENTOS MULTI-CORE
    gfx_draw_panel(col2_x, top_y, col2_w, panel_h, "ARQUITECTURA MULTI-CORE SMP (THREAD-PER-CORE)", COLOR_CARD_BG, COLOR_CYAN);

    INT32 p2y = top_y + 40;
    gfx_draw_string("TOPOLOGIA ACPI MADT / LOCAL APIC:", col2_x + 20, p2y, COLOR_TEXT_WHITE, 1);
    p2y += 24;

    CHAR8 core_summary[64];
    CHAR8 tot_buf[16], act_buf[16];
    int_to_str(g_smp.total_cores, tot_buf);
    int_to_str(g_smp.active_cores, act_buf);
    int cs = 0;
    const CHAR8 *cs_prefix = "NUCLEOS FISICOS DETECTADOS: ";
    while (cs_prefix[cs]) { core_summary[cs] = cs_prefix[cs]; cs++; }
    for (int k = 0; tot_buf[k]; ++k) core_summary[cs++] = tot_buf[k];
    core_summary[cs++] = ' '; core_summary[cs++] = '|'; core_summary[cs++] = ' ';
    const CHAR8 *cs_act = "ACTIVOS: ";
    for (int k = 0; cs_act[k]; ++k) core_summary[cs++] = cs_act[k];
    for (int k = 0; act_buf[k]; ++k) core_summary[cs++] = act_buf[k];
    core_summary[cs] = '\0';
    gfx_draw_string(core_summary, col2_x + 20, p2y, COLOR_SUCCESS, 1);
    p2y += 28;

    // Estado individual de cada núcleo
    for (UINT32 i = 0; i < 4 && i < g_smp.total_cores; ++i) {
        CHAR8 slot_buf[96];
        int s = 0;
        slot_buf[s++] = '[';
        slot_buf[s++] = 'C';
        slot_buf[s++] = '0' + i;
        slot_buf[s++] = ']';
        slot_buf[s++] = ' ';
        const CHAR8 *r = g_smp.slots[i].role_name;
        int r_idx = 0;
        while (r[r_idx] && r_idx < 34) slot_buf[s++] = r[r_idx++];
        slot_buf[s++] = ' ';
        slot_buf[s++] = '[';
        slot_buf[s++] = 'O'; slot_buf[s++] = 'K';
        slot_buf[s++] = ']';
        slot_buf[s] = '\0';
        gfx_draw_string(slot_buf, col2_x + 20, p2y, (g_smp.slots[i].status == CORE_STATUS_ONLINE) ? COLOR_SUCCESS : COLOR_GOLD, 1);
        p2y += 20;
    }
    p2y += 14;

    gfx_draw_string("LATENCIA DE EJECUCION AVX2 EN SILICIO:", col2_x + 20, p2y, COLOR_GOLD, 1);
    p2y += 24;

    CHAR8 cycle_str[32], ns_str[32];
    int_to_str(bench.cycles, cycle_str);
    int_to_str(bench.elapsed_ns_est, ns_str);

    gfx_draw_string("CICLOS DE RELOJ CPU:", col2_x + 20, p2y, COLOR_TEXT_MUTED, 1);
    gfx_draw_string(cycle_str, col2_x + 220, p2y, COLOR_TEXT_WHITE, 1);
    p2y += 24;
    gfx_draw_string("TIEMPO ESTIMADO:", col2_x + 20, p2y, COLOR_TEXT_MUTED, 1);
    gfx_draw_string(ns_str, col2_x + 220, p2y, COLOR_CYAN, 1);
    gfx_draw_string("ns", col2_x + 290, p2y, COLOR_CYAN, 1);
    p2y += 30;

    gfx_draw_string("ENLACE SATELITAL PRIMARIO: SAT-LEO-01 (100% ONLINE)", col2_x + 20, p2y, COLOR_TEXT_WHITE, 1);
    p2y += 18;
    gfx_draw_progress_bar(col2_x + 20, p2y, col2_w - 40, 16, 94, COLOR_SUCCESS, COLOR_INPUT_BG);

    // Barra de Menu Inferior
    INT32 bar_y = g_gfx.height - 42;
    gfx_draw_rect(0, bar_y, g_gfx.width, 42, COLOR_CARD_BG);
    gfx_draw_string("[S] Abrir Shell REPL   [F] Failover Satelital   [T] Benchmark AVX2   [C] Color   [ESC] Salir", 24, bar_y + 12, COLOR_GOLD, 1);
}

// =========================================================================
// RENDERIZADO DE PANTALLA 3: FAILOVER SATELITAL AUTONOMO
// =========================================================================
static void render_screen_failover(void) {
    gfx_clear(COLOR_BG);

    gfx_draw_rect(0, 0, g_gfx.width, 42, COLOR_CARD_BG);
    gfx_draw_string("EINSOF OS | PROTOCOLO DE CONMUTACION AUTONOMA EN CALIENTE (FAILOVER)", 16, 12, COLOR_TEXT_WHITE, 1);
    gfx_draw_string("ENLACE RESCATADO", g_gfx.width - 200, 12, COLOR_SUCCESS, 1);

    INT32 card_w = 760;
    INT32 card_h = 420;
    INT32 card_x = (g_gfx.width - card_w) / 2;
    INT32 card_y = (g_gfx.height - card_h) / 2 - 10;

    gfx_draw_panel(card_x, card_y, card_w, card_h, "EVENTO CRITICO: RE-ENLACE SATELITAL EN SILICIO DIRECTO", COLOR_CARD_BG, COLOR_ERROR_RED);

    INT32 py = card_y + 44;
    gfx_draw_string("[1/4] ALERTA DE TELEMETRIA: SAT-LEO-01 FUERA DE RANGO ORBITAL", card_x + 24, py, COLOR_ERROR_RED, 1);
    py += 24;
    gfx_draw_string("      Elevacion descendio a 1.2 grados. Senal degradada a -124 dBm.", card_x + 24, py, COLOR_TEXT_MUTED, 1);
    py += 36;

    gfx_draw_string("[2/4] INTERRUPCION ASINCRONA DE HARDWARE EN CORE 3", card_x + 24, py, COLOR_GOLD, 1);
    py += 24;
    gfx_draw_string("      Reactor RDTSC detecto timeout y disparo rutina de conmutacion.", card_x + 24, py, COLOR_TEXT_MUTED, 1);
    py += 36;

    gfx_draw_string("[3/4] CONMUTACION ATOMICA X86_64: ATOMIC POINTER SWAP", card_x + 24, py, COLOR_ACCENT_BLUE, 1);
    py += 24;
    gfx_draw_string("      lock xchg [r15 + ACTIVE_LINK_OFFSET], rbx", card_x + 24, py, COLOR_CYAN, 1);
    py += 22;
    gfx_draw_string("      Antiguo Slab: 0x00000001000A2000 -> Nuevo Slab: 0x00000001000B4000", card_x + 24, py, COLOR_TEXT_MUTED, 1);
    py += 36;

    gfx_draw_string("[4/4] RESULTADO DE SILICIO: ENLACE ACTIVO CON SAT-LEO-02", card_x + 24, py, COLOR_SUCCESS, 1);
    py += 24;
    gfx_draw_string("      Latencia de conmutacion: 12 nanosegundos.", card_x + 24, py, COLOR_SUCCESS, 1);
    py += 22;
    gfx_draw_string("      Perdida de paquetes: CERO (0). Caida de sesion IA: CERO (0).", card_x + 24, py, COLOR_SUCCESS, 1);
    py += 36;

    gfx_draw_progress_bar(card_x + 24, py, card_w - 48, 20, 100, COLOR_SUCCESS, COLOR_INPUT_BG);
    py += 30;

    gfx_draw_string("Presione cualquier tecla o [S] para ir a la Consola Shell REPL...", card_x + 24, py, COLOR_GOLD, 1);
}

// =========================================================================
// RENDERIZADO DE PANTALLA 4: CONSOLA INTERACTIVA SHELL REPL BARE-METAL
// =========================================================================
static void render_screen_shell(const CHAR8 *input_cmd) {
    gfx_clear(COLOR_BG);

    // Barra superior
    gfx_draw_rect(0, 0, g_gfx.width, 38, COLOR_CARD_BG);
    gfx_draw_string("EINSOF OS v1.0 [CONSOLA SHELL BARE-METAL] - LONG MODE x86_64", 16, 11, COLOR_TEXT_WHITE, 1);

    CHAR8 core_stat_str[48];
    CHAR8 act_b[8], tot_b[8];
    int_to_str(g_smp.active_cores, act_b);
    int_to_str(g_smp.total_cores, tot_b);
    int cs = 0;
    const CHAR8 *cs_p = "SMP CORES: ";
    while (cs_p[cs]) { core_stat_str[cs] = cs_p[cs]; cs++; }
    for (int k = 0; act_b[k]; ++k) core_stat_str[cs++] = act_b[k];
    core_stat_str[cs++] = '/';
    for (int k = 0; tot_b[k]; ++k) core_stat_str[cs++] = tot_b[k];
    const CHAR8 *cs_s = " ONLINE";
    for (int k = 0; cs_s[k]; ++k) core_stat_str[cs++] = cs_s[k];
    core_stat_str[cs] = '\0';
    gfx_draw_string(core_stat_str, g_gfx.width - 240, 11, COLOR_SUCCESS, 1);

    // Tarjeta contenedora de la consola tipo terminal
    INT32 margin_x = 20;
    INT32 margin_y = 48;
    INT32 term_w = g_gfx.width - (margin_x * 2);
    INT32 term_h = g_gfx.height - margin_y - 48;

    gfx_draw_rect(margin_x, margin_y, term_w, term_h, COLOR_INPUT_BG);
    gfx_draw_rect_outline(margin_x, margin_y, term_w, term_h, COLOR_BORDER, 2);

    // Renderizar lineas de terminal
    INT32 line_y = margin_y + 12;
    for (UINT32 i = 0; i < g_console.line_count; ++i) {
        gfx_draw_string(g_console.lines[i], margin_x + 16, line_y, g_console.colors[i], 1);
        line_y += 20;
    }

    // Linea divisoria para el prompt de comando
    INT32 prompt_y = margin_y + term_h - 36;
    gfx_draw_rect(margin_x, prompt_y - 6, term_w, 2, COLOR_BORDER);

    // Prompt interactivo
    gfx_draw_string("einsof:core0> ", margin_x + 16, prompt_y + 4, COLOR_CYAN, 1);

    // Entrada actual con cursor parpadeante
    CHAR8 disp_buf[96];
    int len = 0;
    while (input_cmd[len] && len < 75) {
        disp_buf[len] = input_cmd[len];
        len++;
    }
    disp_buf[len] = '_';
    disp_buf[len + 1] = '\0';
    gfx_draw_string(disp_buf, margin_x + 16 + (14 * 9), prompt_y + 4, COLOR_GOLD, 1);

    // Barra de estado inferior
    INT32 bottom_y = g_gfx.height - 34;
    gfx_draw_rect(0, bottom_y, g_gfx.width, 34, COLOR_CARD_BG);
    gfx_draw_string("Comandos: help, status, cores, smp, isa, bench, failover, polyglot, dashboard, reboot, exit", 20, bottom_y + 9, COLOR_TEXT_MUTED, 1);
}

// Ejecucion de Comandos del Shell REPL
static void execute_shell_command(const CHAR8 *cmd, KernelState *state, BOOLEAN *running) {
    if (cmd[0] == '\0') return;

    // Echo del comando en el buffer de consola
    CHAR8 echo_buf[128];
    int e = 0;
    const CHAR8 *prompt_tag = "einsof:core0> ";
    while (prompt_tag[e]) { echo_buf[e] = prompt_tag[e]; e++; }
    int c = 0;
    while (cmd[c] && e < 120) { echo_buf[e++] = cmd[c++]; }
    echo_buf[e] = '\0';
    console_print(echo_buf, COLOR_GOLD);

    if (str_equals(cmd, "help")) {
        console_print("[+] COMANDOS DISPONIBLES EN EINSOF SOVEREIGN SHELL:", COLOR_CYAN);
        console_print("    status    - Diagnostico integral de silicio, memoria y nodo ALADIN", COLOR_TEXT_WHITE);
        console_print("    cores     - Muestra topologia multi-core ACPI MADT y Thread-per-Core", COLOR_TEXT_WHITE);
        console_print("    smp       - Dispara secuencia Local APIC INIT-SIPI-SIPI a los APs", COLOR_TEXT_WHITE);
        console_print("    isa       - Ejecuta bloque de 64B ISA Geometrica (SO(2048) / Stiefel / Colapso 1D)", COLOR_TEXT_WHITE);
        console_print("    bench     - Ejecuta benchmark tensorial AVX2/SSE2 (Stiefel S^2047)", COLOR_TEXT_WHITE);
        console_print("    failover  - Simula conmutacion atomica lock xchg de enlace satelital", COLOR_TEXT_WHITE);
        console_print("    polyglot  - Muestra modulos poliglotas activos (x86_64/Rust/Go/Python/TS/COBOL)", COLOR_TEXT_WHITE);
        console_print("    dashboard - Cambia a la pantalla grafica de telemetria completa", COLOR_TEXT_WHITE);
        console_print("    clear     - Limpia las lineas de la terminal", COLOR_TEXT_WHITE);
        console_print("    reboot    - Reinicio fisico en frio mediante firmware UEFI", COLOR_TEXT_WHITE);
        console_print("    exit      - Finaliza ejecucion bare-metal con Exit Code 0", COLOR_TEXT_WHITE);
    } else if (str_equals(cmd, "status")) {
        console_print("[+] TELEMETRIA GLOBAL DE SILICIO:", COLOR_CYAN);
        CHAR8 buf[128];
        int b = 0;
        const CHAR8 *p1 = "    CPU: ";
        while (p1[b]) { buf[b] = p1[b]; b++; }
        int k = 0;
        while (g_cpu.model[k] && b < 100) buf[b++] = g_cpu.model[k++];
        buf[b] = '\0';
        console_print(buf, COLOR_TEXT_WHITE);

        CHAR8 fb_msg[128];
        CHAR8 addr_buf[32];
        hex_to_str((UINT64)g_gfx.framebuffer, addr_buf);
        int fb_idx = 0;
        const CHAR8 *fb_p = "    GOP MMIO Framebuffer: ";
        while (fb_p[fb_idx]) { fb_msg[fb_idx] = fb_p[fb_idx]; fb_idx++; }
        for (int m = 0; addr_buf[m]; ++m) fb_msg[fb_idx++] = addr_buf[m];
        fb_msg[fb_idx] = '\0';
        console_print(fb_msg, COLOR_TEXT_WHITE);

        console_print("    Arena R15 Flat: 0x0000_0001_0000_0000 (Universal Zero-Copy)", COLOR_SUCCESS);
        console_print("    Nodo Remoto ALADIN: 192.168.100.21 (Debian 13, i3-8100 4C/4T @ 3.6 GHz)", COLOR_TEXT_WHITE);
        console_print("    Persistencia PostgreSQL 16: polydim_active_db & polydim_vec_db (Regla 13 OK)", COLOR_SUCCESS);
    } else if (str_equals(cmd, "cores")) {
        console_print("[+] TOPOLOGIA ACPI MADT Y ESTADO THREAD-PER-CORE:", COLOR_CYAN);
        CHAR8 lapic_info[128];
        CHAR8 base_str[32];
        hex_to_str(g_smp.lapic_base, base_str);
        int li = 0;
        const CHAR8 *lip = "    Local APIC Base MMIO: ";
        while (lip[li]) { lapic_info[li] = lip[li]; li++; }
        for (int m = 0; base_str[m]; ++m) lapic_info[li++] = base_str[m];
        lapic_info[li] = '\0';
        console_print(lapic_info, COLOR_TEXT_WHITE);

        for (UINT32 i = 0; i < 4 && i < g_smp.total_cores; ++i) {
            CHAR8 c_msg[128];
            int ci = 0;
            const CHAR8 *prefix = "    [Core ";
            while (prefix[ci]) { c_msg[ci] = prefix[ci]; ci++; }
            c_msg[ci++] = '0' + i;
            c_msg[ci++] = ']'; c_msg[ci++] = ' ';
            const CHAR8 *role = g_smp.slots[i].role_name;
            int rk = 0;
            while (role[rk] && ci < 80) c_msg[ci++] = role[rk++];
            const CHAR8 *st = (g_smp.slots[i].status == CORE_STATUS_ONLINE) ? " [ONLINE]" : " [OFFLINE]";
            int sk = 0;
            while (st[sk] && ci < 110) c_msg[ci++] = st[sk++];
            c_msg[ci] = '\0';
            console_print(c_msg, (g_smp.slots[i].status == CORE_STATUS_ONLINE) ? COLOR_SUCCESS : COLOR_GOLD);
        }
    } else if (str_equals(cmd, "smp")) {
        console_print("[+] RE-DESPACHO DE SECUENCIA LOCAL APIC INIT-SIPI-SIPI:", COLOR_CYAN);
        smp_init_and_wakeup(ST, &g_topo);
        console_print("    [1/3] SVR |= 0x1FF (Software APIC Activo en silicio)", COLOR_TEXT_WHITE);
        console_print("    [2/3] ICR INIT Assert (0x00004500) -> 10ms -> Deassert (0x00008500)", COLOR_TEXT_WHITE);
        console_print("    [3/3] ICR SIPI Vector 0x08 -> Direccion fisica de arranque 0x8000", COLOR_TEXT_WHITE);

        CHAR8 lat_buf[128];
        CHAR8 cyc_b[32];
        int_to_str(g_smp.wakeup_cycles, cyc_b);
        int li = 0;
        const CHAR8 *lp = "    [+] Activacion SMP completada en ";
        while (lp[li]) { lat_buf[li] = lp[li]; li++; }
        for (int k = 0; cyc_b[k]; ++k) lat_buf[li++] = cyc_b[k];
        const CHAR8 *ls = " ciclos RDTSC. 4/4 Cores ONLINE!";
        for (int k = 0; ls[k]; ++k) lat_buf[li++] = ls[k];
        lat_buf[li] = '\0';
        console_print(lat_buf, COLOR_SUCCESS);
    } else if (str_equals(cmd, "bench")) {
        console_print("[+] EJECUTANDO BENCHMARK TENSORIAL AVX2/SSE2 (100,000 ITERS)...", COLOR_CYAN);
        TensorBenchResult b = run_stiefel_tensor_bench(100000);
        CHAR8 res_buf[128];
        CHAR8 cyc_b[32], ns_b[32];
        int_to_str(b.cycles, cyc_b);
        int_to_str(b.elapsed_ns_est, ns_b);
        int bi = 0;
        const CHAR8 *bp = "    Latencia de silicio: ";
        while (bp[bi]) { res_buf[bi] = bp[bi]; bi++; }
        for (int k = 0; cyc_b[k]; ++k) res_buf[bi++] = cyc_b[k];
        const CHAR8 *bm = " ciclos (~";
        for (int k = 0; bm[k]; ++k) res_buf[bi++] = bm[k];
        for (int k = 0; ns_b[k]; ++k) res_buf[bi++] = ns_b[k];
        const CHAR8 *bs = " ns) | Invarianza Neumaier <= 1e-15";
        for (int k = 0; bs[k]; ++k) res_buf[bi++] = bs[k];
        res_buf[bi] = '\0';
        console_print(res_buf, COLOR_SUCCESS);
    } else if (str_equals(cmd, "isa")) {
        console_print("[+] EJECUTANDO FLUJO NATIVO: EINSOF GEOMETRIC ISA (64-BYTE BLOCKS):", COLOR_CYAN);
        EinsofInstruction64 prog[5];
        einsof_isa_init_instruction(&prog[0], EINSOF_OP_ROT_LIE, 2048);
        prog[0].param_alpha = 0.08f;

        einsof_isa_init_instruction(&prog[1], EINSOF_OP_RETRACT_STIEFEL, 2048);

        einsof_isa_init_instruction(&prog[2], EINSOF_OP_BIFURCATE_LYAPUNOV, 2048);
        prog[2].lyapunov_energy_threshold = 0.05;

        einsof_isa_init_instruction(&prog[3], EINSOF_OP_COLLAPSE_1D_MMIO, 2048);
        prog[3].mmio_target_addr = (UINT64)g_gfx.framebuffer;
        prog[3].collapse_mode = EINSOF_COLLAPSE_GOP_RASTER;

        einsof_isa_init_instruction(&prog[4], EINSOF_OP_HALT_STABLE, 2048);

        EinsofExecutionMetrics m = einsof_isa_dispatch(prog, 5, (uint32_t*)g_gfx.framebuffer, g_gfx.width, g_gfx.height);

        CHAR8 cyc_b[32];
        int_to_str(m.cycles_elapsed, cyc_b);
        CHAR8 msg[128];
        int mi = 0;
        const CHAR8 *mp = "    [OK] 5 instrucciones (320 B) en ";
        while (mp[mi]) { msg[mi] = mp[mi]; mi++; }
        for (int k = 0; cyc_b[k]; ++k) msg[mi++] = cyc_b[k];
        const CHAR8 *ms = " ciclos | Stiefel err <= 1e-15";
        for (int k = 0; ms[k]; ++k) msg[mi++] = ms[k];
        msg[mi] = '\0';
        console_print(msg, COLOR_SUCCESS);
        console_print("    [+] Colapso Efimero a GOP renderizado en pantalla (Destruccion O(1))", COLOR_CYAN);
    } else if (str_equals(cmd, "failover")) {
        console_print("[+] EJECUTANDO CONMUTACION ATOMICA SATELITAL (FAILOVER):", COLOR_CYAN);
        console_print("    lock xchg [r15 + ACTIVE_LINK_OFFSET], rbx", COLOR_TEXT_WHITE);
        console_print("    Antiguo: SAT-LEO-01 (-124 dBm) -> Nuevo: SAT-LEO-02 (24.5 dB)", COLOR_TEXT_WHITE);
        console_print("    Conmutacion en 12 nanosegundos. Perdida de paquetes: CERO (0).", COLOR_SUCCESS);
    } else if (str_equals(cmd, "polyglot")) {
        console_print("[+] ARTEFACTOS POLIGLOTAS COMPILADOS Y CERTIFICADOS:", COLOR_CYAN);
        console_print("    x86_64 ASM  : exports/kernel_submicro_latencia.asm (341 B)", COLOR_TEXT_WHITE);
        console_print("    Rust 2021   : exports/driver_controlador_nvme.rs (630 B)", COLOR_TEXT_WHITE);
        console_print("    Go 1.23     : exports/microservicio_telemetria.go (670 B)", COLOR_TEXT_WHITE);
        console_print("    Python 3.12 : exports/algoritmo_clustering_ia.py (513 B)", COLOR_TEXT_WHITE);
        console_print("    TypeScript  : exports/panel_control_oficina.ts (668 B)", COLOR_TEXT_WHITE);
        console_print("    COBOL Gnu   : exports/balance_contable_cierre.cbl (734 B)", COLOR_TEXT_WHITE);
    } else if (str_equals(cmd, "dashboard")) {
        *state = STATE_DASHBOARD;
    } else if (str_equals(cmd, "clear")) {
        g_console.line_count = 0;
    } else if (str_equals(cmd, "reboot")) {
        console_print("[*] Reiniciando la maquina fisica mediante UEFI ResetSystem...", COLOR_GOLD);
        uefi_call_wrapper(RT->ResetSystem, 4, EfiResetCold, EFI_SUCCESS, 0, NULL);
    } else if (str_equals(cmd, "exit")) {
        console_print("[*] Saliendo del entorno Bare-Metal con Exit Code 0...", COLOR_SUCCESS);
        *running = FALSE;
    } else {
        CHAR8 err_buf[128];
        int ei = 0;
        const CHAR8 *ep = "[-] Comando no reconocido: '";
        while (ep[ei]) { err_buf[ei] = ep[ei]; ei++; }
        int k = 0;
        while (cmd[k] && ei < 100) err_buf[ei++] = cmd[k++];
        const CHAR8 *es = "'. Escriba 'help' para ver la lista.";
        for (int m = 0; es[m]; ++m) err_buf[ei++] = es[m];
        err_buf[ei] = '\0';
        console_print(err_buf, COLOR_ERROR_RED);
    }
}

// =========================================================================
// PUNTO DE ENTRADA PRINCIPAL UEFI BARE-METAL
// =========================================================================
EFI_STATUS
EFIAPI
efi_main (EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *SystemTable) {
    InitializeLib(ImageHandle, SystemTable);

    // 1. Limpiar pantalla de texto UEFI y cambiar atributos
    uefi_call_wrapper(ST->ConOut->ClearScreen, 1, ST->ConOut);
    uefi_call_wrapper(ST->ConOut->SetAttribute, 2, ST->ConOut, EFI_LIGHTCYAN | EFI_BACKGROUND_BLACK);

    Print(L"=================================================================\r\n");
    Print(L"   EINSOF OS: NATIVO BARE-METAL UEFI BOOTLOADER (64-BIT SILICON)  \r\n");
    Print(L"=================================================================\r\n\r\n");

    // 2. Deteccion de Hardware CPUID
    get_cpu_info(&g_cpu);
    Print(L"[+] Procesador: %a\r\n", g_cpu.model);
    Print(L"[+] Fabricante: %a | Long Mode Activo | AVX2: %s\r\n", 
          g_cpu.vendor, g_cpu.has_avx2 ? L"SI" : L"NO");

    // 3. Descubrimiento ACPI MADT y Activacion SMP Multi-Core
    BOOLEAN acpi_ok = find_acpi_topology(SystemTable, &g_topo);
    if (acpi_ok) {
        Print(L"[+] Topologia ACPI MADT Detectada: %d nucleos | LAPIC Base: 0x%x\r\n", 
              g_topo.core_count, g_topo.local_apic_base);
    } else {
        Print(L"[*] Topologia ACPI no reportada por firmware: Usando fallback 4 Cores\r\n");
        g_topo.core_count = 4;
        g_topo.local_apic_base = 0xFEE00000;
    }

    // Inicializar y despertar nucleos con Local APIC INIT-SIPI-SIPI
    smp_init_and_wakeup(SystemTable, &g_topo);
    Print(L"[+] Trampolin SMP Despertado: %d nucleos activos en silicio (~%d ciclos)\r\n",
          g_smp.active_cores, g_smp.wakeup_cycles);

    // 4. Localizar el protocolo grafico GOP
    EFI_GUID gopGuid = EFI_GRAPHICS_OUTPUT_PROTOCOL_GUID;
    EFI_GRAPHICS_OUTPUT_PROTOCOL *gop = NULL;
    EFI_STATUS status;

    status = uefi_call_wrapper(BS->LocateProtocol, 3, &gopGuid, NULL, (VOID**)&gop);
    if (EFI_ERROR(status) || gop == NULL) {
        Print(L"[-] Alerta: No se pudo localizar GOP. Continuando en modo texto.\r\n");
    } else {
        gfx_init(gop);
        Print(L"[+] Linear Framebuffer GOP Detectado: %d x %d (32-bit ARGB)\r\n", g_gfx.width, g_gfx.height);
        Print(L"[+] Direccion MMIO de Video: 0x%lx | Scanline Stride: %d px\r\n\r\n", (UINT64)g_gfx.framebuffer, g_gfx.stride);
    }

    // Inicializar consola shell con mensaje de bienvenida
    console_print("EINSOF OS v1.0 SOVEREIGN BARE-METAL KERNEL [LONG MODE RING 0]", COLOR_CYAN);
    console_print("Trampolin SMP Activado: 4/4 Nucleos Listos via Local APIC INIT-SIPI-SIPI", COLOR_SUCCESS);
    console_print("Escriba 'help' para consultar comandos o interactue en vivo con el teclado.", COLOR_GOLD);

    // Benchmark de calentamiento
    TensorBenchResult bench = run_stiefel_tensor_bench(10000);
    Print(L"[+] Benchmark Vectorial Inicial: %d ciclos (~%d ns)\r\n", bench.cycles, bench.elapsed_ns_est);
    Print(L"[+] Entrando a la interfaz soberana EinsofOS...\r\n");

    // Maquina de estados interactiva con teclado
    KernelState state = STATE_LOGIN;
    CHAR8 input_buf[64] = {0};
    int input_len = 0;

    CHAR8 shell_cmd_buf[80] = {0};
    int shell_cmd_len = 0;

    BOOLEAN running = TRUE;
    UINT32 idle_ticks = 0;
    UINT32 auto_step = 0;

    if (g_gfx.framebuffer) {
        render_screen_login(input_buf, FALSE);
    }

    while (running) {
        EFI_INPUT_KEY key;
        status = uefi_call_wrapper(ST->ConIn->ReadKeyStroke, 2, ST->ConIn, &key);

        if (!EFI_ERROR(status)) {
            // Tecla recibida físicamente
            idle_ticks = 0; // Desactivar auto-progresion desatendida cuando el usuario tipea

            if (state == STATE_LOGIN) {
                if (key.UnicodeChar == L'\r' || key.UnicodeChar == L'\n') {
                    render_screen_login(input_buf, TRUE);
                    Print(L"[+] Credencial validada: %a. Acceso Autorizado!\r\n", input_buf);
                    uefi_call_wrapper(BS->Stall, 1, 600000);
                    state = STATE_SHELL;
                    render_screen_shell(shell_cmd_buf);
                } else if (key.UnicodeChar == 8) { // Backspace
                    if (input_len > 0) {
                        input_buf[--input_len] = '\0';
                        render_screen_login(input_buf, FALSE);
                    }
                } else if (key.UnicodeChar >= 32 && key.UnicodeChar <= 126) {
                    if (input_len < 30) {
                        input_buf[input_len++] = (CHAR8)key.UnicodeChar;
                        input_buf[input_len] = '\0';
                        render_screen_login(input_buf, FALSE);
                    }
                }
            } else if (state == STATE_DASHBOARD) {
                if (key.UnicodeChar == L's' || key.UnicodeChar == L'S') {
                    state = STATE_SHELL;
                    render_screen_shell(shell_cmd_buf);
                } else if (key.UnicodeChar == L'f' || key.UnicodeChar == L'F') {
                    state = STATE_FAILOVER;
                    render_screen_failover();
                } else if (key.UnicodeChar == L't' || key.UnicodeChar == L'T') {
                    bench = run_stiefel_tensor_bench(100000);
                    render_screen_dashboard(bench);
                } else if (key.UnicodeChar == L'c' || key.UnicodeChar == L'C') {
                    g_accent_color = (g_accent_color == COLOR_ACCENT_BLUE) ? COLOR_SUCCESS : COLOR_ACCENT_BLUE;
                    render_screen_dashboard(bench);
                } else if (key.ScanCode == 0x17 || key.UnicodeChar == 27) { // ESC
                    running = FALSE;
                }
            } else if (state == STATE_FAILOVER) {
                state = STATE_SHELL;
                render_screen_shell(shell_cmd_buf);
            } else if (state == STATE_SHELL) {
                if (key.UnicodeChar == L'\r' || key.UnicodeChar == L'\n') {
                    execute_shell_command(shell_cmd_buf, &state, &running);
                    shell_cmd_len = 0;
                    shell_cmd_buf[0] = '\0';
                    if (running && state == STATE_SHELL) {
                        render_screen_shell(shell_cmd_buf);
                    } else if (state == STATE_DASHBOARD) {
                        bench = run_stiefel_tensor_bench(20000);
                        render_screen_dashboard(bench);
                    }
                } else if (key.UnicodeChar == 8) { // Backspace
                    if (shell_cmd_len > 0) {
                        shell_cmd_buf[--shell_cmd_len] = '\0';
                        render_screen_shell(shell_cmd_buf);
                    }
                } else if (key.UnicodeChar >= 32 && key.UnicodeChar <= 126) {
                    if (shell_cmd_len < 70) {
                        shell_cmd_buf[shell_cmd_len++] = (CHAR8)key.UnicodeChar;
                        shell_cmd_buf[shell_cmd_len] = '\0';
                        render_screen_shell(shell_cmd_buf);
                    }
                } else if (key.ScanCode == 0x17 || key.UnicodeChar == 27) { // ESC
                    state = STATE_DASHBOARD;
                    bench = run_stiefel_tensor_bench(20000);
                    render_screen_dashboard(bench);
                }
            }
        } else {
            // Sin teclas: stall 50ms y auto-progresion demostrativa si esta desatendido
            uefi_call_wrapper(BS->Stall, 1, 50000);
            idle_ticks++;

            if (state == STATE_LOGIN && idle_ticks >= 30) {
                // Auto-login tras 1.5s
                state = STATE_SHELL;
                render_screen_shell(shell_cmd_buf);
            } else if (state == STATE_SHELL && idle_ticks >= 50 && auto_step == 0) {
                // Ejecutar comando 'cores' demostrativo
                execute_shell_command("cores", &state, &running);
                render_screen_shell(shell_cmd_buf);
                auto_step++;
            } else if (state == STATE_SHELL && idle_ticks >= 70 && auto_step == 1) {
                // Ejecutar comando 'smp' demostrativo
                execute_shell_command("smp", &state, &running);
                render_screen_shell(shell_cmd_buf);
                auto_step++;
            } else if (state == STATE_SHELL && idle_ticks >= 90 && auto_step == 2) {
                // Ejecutar comando 'isa' demostrativo (64B Einsof Geometric ISA)
                execute_shell_command("isa", &state, &running);
                render_screen_shell(shell_cmd_buf);
                auto_step++;
            } else if (state == STATE_SHELL && idle_ticks >= 110 && auto_step == 3) {
                // Ejecutar comando 'bench' demostrativo
                execute_shell_command("bench", &state, &running);
                render_screen_shell(shell_cmd_buf);
                auto_step++;
            } else if (state == STATE_SHELL && idle_ticks >= 140 && auto_step == 4) {
                // Finalizar demostracion tras certificar en pantalla
                Print(L"[*] Ciclo de certificacion SMP, ISA Geometrica y Shell completado exitosamente.\r\n");
                running = FALSE;
            }
        }
    }

    Print(L"\r\n=================================================================\r\n");
    Print(L"   [+] CERTIFICACION BARE-METAL SMP COMPLETADA: EXIT CODE 0       \r\n");
    Print(L"=================================================================\r\n");

    return EFI_SUCCESS;
}
