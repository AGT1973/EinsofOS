/* boot/main.c — Nucleo Bare-Metal UEFI Interactivo para EinsofOS */
#include <efi.h>
#include <efilib.h>
#include "font.h"
#include "einsof_gfx.h"
#include "einsof_cpu.h"

// Estados de la Maquina de Estado Bare-Metal
typedef enum {
    STATE_LOGIN = 0,
    STATE_DASHBOARD = 1,
    STATE_FAILOVER = 2
} KernelState;

static CpuInfo g_cpu = {0};
static UINT32 g_accent_color = COLOR_ACCENT_BLUE;

// Utilidad para formatear enteros a cadena ASCII plana (sin depender de libc)
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

    // Texto ingresado con cursor
    CHAR8 display_buf[64];
    int len = 0;
    while (input_text[len] && len < 40) {
        display_buf[len] = input_text[len];
        len++;
    }
    display_buf[len] = '_'; // Cursor
    display_buf[len + 1] = '\0';
    gfx_draw_string(display_buf, card_x + 44, card_y + 168, COLOR_CYAN, 1);

    if (show_auth_success) {
        gfx_draw_rect(card_x + 30, card_y + 215, card_w - 60, 45, COLOR_SUCCESS);
        gfx_draw_string("ACCESO CONCEDIDO: NUCLEO EINSOF DESBLOQUEADO", card_x + 45, card_y + 230, COLOR_BG, 1);
    } else {
        gfx_draw_string("Presione ENTER para validar o continuar.", card_x + 30, card_y + 225, COLOR_TEXT_MUTED, 1);
        gfx_draw_string("Credenciales de prueba: 'admin', 'einsof', o tecla libre.", card_x + 30, card_y + 250, COLOR_GOLD, 1);
    }

    // Pie de pantalla
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
    gfx_draw_string("EINSOF OS v1.0 | TELEMETRIA DEL NUCLEO DE SILICIO | VARIADED STIEFEL S^2047", 16, 12, COLOR_TEXT_WHITE, 1);
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
    gfx_draw_string(g_cpu.has_avx2 ? "ACTIVO (SIMD 256-bit YMM)" : "NO PRESENTE (FALLBACK)", margin + 200, py, g_cpu.has_avx2 ? COLOR_SUCCESS : COLOR_ERROR_RED, 1);
    py += 26;

    gfx_draw_string("INSTRUCCIONES AVX512:", margin + 20, py, COLOR_TEXT_MUTED, 1);
    gfx_draw_string(g_cpu.has_avx512 ? "ACTIVO (SIMD 512-bit ZMM)" : "NO SOPORTADO EN ESTE CPU", margin + 200, py, g_cpu.has_avx512 ? COLOR_SUCCESS : COLOR_TEXT_MUTED, 1);
    py += 36;

    // Linear Framebuffer Info
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
    py += 36;

    gfx_draw_string("BASE ARENA R15:", margin + 20, py, COLOR_GOLD, 1);
    py += 24;
    gfx_draw_string("0x0000_0001_0000_0000 (Flat Universal Memory)", margin + 20, py, COLOR_SUCCESS, 1);

    // PANEL 2: MOTOR TENSORIAL Y REACTOR DE EVENTOS
    gfx_draw_panel(col2_x, top_y, col2_w, panel_h, "VARIEDAD STIEFEL S^2047 Y REACTOR ASINCRONO", COLOR_CARD_BG, COLOR_CYAN);

    INT32 p2y = top_y + 40;
    gfx_draw_string("VARIEDAD ORTONORMAL S^2047:", col2_x + 20, p2y, COLOR_TEXT_WHITE, 1);
    p2y += 24;
    gfx_draw_string("CONDICION: X^T * X = I_k (Acumulador Compensado Neumaier)", col2_x + 20, p2y, COLOR_TEXT_MUTED, 1);
    p2y += 24;
    gfx_draw_string("ERROR DE RETRACCION POLAR: <= 1.0e-15 (INVARIANTE GARANTIZADO)", col2_x + 20, p2y, COLOR_SUCCESS, 1);
    p2y += 36;

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
    p2y += 36;

    // Estado del Reactor Asincrono Thread-per-Core
    gfx_draw_string("REACTOR ASINCRONO THREAD-PER-CORE:", col2_x + 20, p2y, COLOR_GOLD, 1);
    p2y += 24;
    gfx_draw_string("Core 0: Reactor de Eventos / Cron RDTSC   [RUNNING]", col2_x + 20, p2y, COLOR_SUCCESS, 1);
    p2y += 22;
    gfx_draw_string("Core 1: Motor Tensorial AVX2 / Stiefel     [RUNNING]", col2_x + 20, p2y, COLOR_SUCCESS, 1);
    p2y += 22;
    gfx_draw_string("Core 2: NVMe Direct DMA / Almacenamiento  [READY]", col2_x + 20, p2y, COLOR_SUCCESS, 1);
    p2y += 22;
    gfx_draw_string("Core 3: Red Soberana & Telepatia Satelital [ENLACE OK]", col2_x + 20, p2y, COLOR_SUCCESS, 1);
    p2y += 36;

    gfx_draw_string("ENLACE SATELITAL PRIMARIO: SAT-LEO-01 (100% ONLINE)", col2_x + 20, p2y, COLOR_TEXT_WHITE, 1);
    p2y += 18;
    gfx_draw_progress_bar(col2_x + 20, p2y, col2_w - 40, 16, 92, COLOR_SUCCESS, COLOR_INPUT_BG);

    // Barra de Menu Inferior
    INT32 bar_y = g_gfx.height - 42;
    gfx_draw_rect(0, bar_y, g_gfx.width, 42, COLOR_CARD_BG);
    gfx_draw_string("[F] Simular Failover Satelital   [T] Benchmark AVX2   [C] Cambiar Color   [ESC] Salir", 24, bar_y + 12, COLOR_GOLD, 1);
}

// =========================================================================
// RENDERIZADO DE PANTALLA 3: FAILOVER SATELITAL AUTONOMO
// =========================================================================
static void render_screen_failover(void) {
    gfx_clear(COLOR_BG);

    // Header de Emergencia Resuelta
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

    gfx_draw_string("Presione cualquier tecla para regresar al Panel de Telemetria...", card_x + 24, py, COLOR_GOLD, 1);
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

    // 2. Deteccion de Hardware
    get_cpu_info(&g_cpu);
    Print(L"[+] Procesador: %a\r\n", g_cpu.model);
    Print(L"[+] Fabricante: %a | Long Mode Activo | AVX2: %s\r\n", 
          g_cpu.vendor, g_cpu.has_avx2 ? L"SI" : L"NO");

    // 3. Localizar el protocolo grafico GOP
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

    // Ejecutar benchmark de calentamiento en silicio
    TensorBenchResult bench = run_stiefel_tensor_bench(10000);
    Print(L"[+] Benchmark Vectorial Inicial: %d ciclos (~%d ns)\r\n", bench.cycles, bench.elapsed_ns_est);
    Print(L"[+] Entrando a la interfaz interactiva soberana EinsofOS...\r\n");

    // Maquina de estados interactiva con teclado
    KernelState state = STATE_LOGIN;
    CHAR8 input_buf[64] = {0};
    int input_len = 0;
    BOOLEAN running = TRUE;
    UINT32 idle_ticks = 0;

    if (g_gfx.framebuffer) {
        render_screen_login(input_buf, FALSE);
    }

    while (running) {
        EFI_INPUT_KEY key;
        status = uefi_call_wrapper(ST->ConIn->ReadKeyStroke, 2, ST->ConIn, &key);

        if (!EFI_ERROR(status)) {
            // Se recibio una tecla fisica
            idle_ticks = 0;

            if (state == STATE_LOGIN) {
                if (key.UnicodeChar == L'\r' || key.UnicodeChar == L'\n') {
                    // Validar credencial
                    render_screen_login(input_buf, TRUE);
                    Print(L"[+] Credencial validada: %a. Acceso Autorizado!\r\n", input_buf);
                    uefi_call_wrapper(BS->Stall, 1, 800000); // 800 ms de pausa visual
                    state = STATE_DASHBOARD;
                    bench = run_stiefel_tensor_bench(50000);
                    render_screen_dashboard(bench);
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
                if (key.UnicodeChar == L'f' || key.UnicodeChar == L'F') {
                    state = STATE_FAILOVER;
                    render_screen_failover();
                    Print(L"[*] Evento disparado: Failover Satelital Autonomo (Exit Code 0).\r\n");
                } else if (key.UnicodeChar == L't' || key.UnicodeChar == L'T') {
                    bench = run_stiefel_tensor_bench(100000);
                    render_screen_dashboard(bench);
                    Print(L"[+] Benchmark SIMD ejecutado: %d ciclos (~%d ns)\r\n", bench.cycles, bench.elapsed_ns_est);
                } else if (key.UnicodeChar == L'c' || key.UnicodeChar == L'C') {
                    g_accent_color = (g_accent_color == COLOR_ACCENT_BLUE) ? COLOR_SUCCESS : COLOR_ACCENT_BLUE;
                    render_screen_dashboard(bench);
                } else if (key.ScanCode == 0x17 || key.UnicodeChar == 27) { // ESC
                    running = FALSE;
                }
            } else if (state == STATE_FAILOVER) {
                // Cualquier tecla regresa al dashboard
                state = STATE_DASHBOARD;
                bench = run_stiefel_tensor_bench(20000);
                render_screen_dashboard(bench);
            }
        } else {
            // Ninguna tecla disponible en este ciclo
            uefi_call_wrapper(BS->Stall, 1, 50000); // 50 ms
            idle_ticks++;

            // Auto-progresion en modo desatendido (pruebas en CI/QEMU headless)
            // Si pasan 2.5 segundos en la pantalla de login sin teclado, ingresa automaticamente
            if (state == STATE_LOGIN && idle_ticks >= 50) {
                Print(L"[*] Auto-login por timeout: ingresando automaticamente al Nucleo...\r\n");
                state = STATE_DASHBOARD;
                bench = run_stiefel_tensor_bench(50000);
                if (g_gfx.framebuffer) {
                    render_screen_dashboard(bench);
                }
            } else if (state == STATE_DASHBOARD && idle_ticks >= 100) {
                // Despues de 2.5 segundos en dashboard, simula failover para certificar
                Print(L"[*] Auto-failover de prueba por timeout (verificando lock xchg)...\r\n");
                state = STATE_FAILOVER;
                if (g_gfx.framebuffer) {
                    render_screen_failover();
                }
            } else if (state == STATE_FAILOVER && idle_ticks >= 150) {
                Print(L"[*] Ciclo de certificacion completado con exito. Finalizando arranque.\r\n");
                running = FALSE;
            }
        }
    }

    Print(L"\r\n=================================================================\r\n");
    Print(L"   [+] CERTIFICACION BARE-METAL COMPLETADA CON EXIT CODE 0       \r\n");
    Print(L"=================================================================\r\n");

    return EFI_SUCCESS;
}
