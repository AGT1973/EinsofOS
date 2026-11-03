/* einsof_gfx.h — Motor Grafico GOP Bare-Metal para EinsofOS */
#ifndef EINSOF_GFX_H
#define EINSOF_GFX_H

#include <efi.h>
#include <efilib.h>
#include "font.h"

// Paleta Oficial EinsofOS (Formato 32-bit ARGB / XRGB)
#define COLOR_BG          0x001E1E2E
#define COLOR_CARD_BG     0x002A2B3C
#define COLOR_INPUT_BG    0x00181825
#define COLOR_TEXT_WHITE  0x00CDD6F4
#define COLOR_TEXT_MUTED  0x00A6ADC8
#define COLOR_ACCENT_BLUE 0x0089B4FA
#define COLOR_SUCCESS     0x00A6E3A1
#define COLOR_WARNING     0x00F9E2AF
#define COLOR_ERROR_RED   0x00F38BA8
#define COLOR_BORDER      0x0045475A
#define COLOR_CYAN        0x0094E2D5
#define COLOR_GOLD        0x00F9E2AF

typedef struct {
    UINT32 *framebuffer;
    UINT32 width;
    UINT32 height;
    UINT32 stride; // Pixels per scanline
    UINTN  size;
} GfxContext;

static GfxContext g_gfx = {0};

static inline void gfx_init(EFI_GRAPHICS_OUTPUT_PROTOCOL *gop) {
    if (!gop || !gop->Mode || !gop->Mode->Info) return;
    g_gfx.framebuffer = (UINT32*)(UINTN)gop->Mode->FrameBufferBase;
    g_gfx.width = gop->Mode->Info->HorizontalResolution;
    g_gfx.height = gop->Mode->Info->VerticalResolution;
    g_gfx.stride = gop->Mode->Info->PixelsPerScanLine;
    g_gfx.size = gop->Mode->FrameBufferSize;
}

static inline void gfx_put_pixel(INT32 x, INT32 y, UINT32 color) {
    if (x < 0 || x >= (INT32)g_gfx.width || y < 0 || y >= (INT32)g_gfx.height) return;
    g_gfx.framebuffer[y * g_gfx.stride + x] = color;
}

static inline void gfx_clear(UINT32 color) {
    if (!g_gfx.framebuffer) return;
    for (UINT32 y = 0; y < g_gfx.height; ++y) {
        UINT32 row = y * g_gfx.stride;
        for (UINT32 x = 0; x < g_gfx.width; ++x) {
            g_gfx.framebuffer[row + x] = color;
        }
    }
}

static inline void gfx_draw_rect(INT32 x, INT32 y, INT32 w, INT32 h, UINT32 color) {
    if (!g_gfx.framebuffer) return;
    INT32 x2 = x + w;
    INT32 y2 = y + h;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    if (x2 > (INT32)g_gfx.width) x2 = (INT32)g_gfx.width;
    if (y2 > (INT32)g_gfx.height) y2 = (INT32)g_gfx.height;

    for (INT32 cy = y; cy < y2; ++cy) {
        UINT32 row = cy * g_gfx.stride;
        for (INT32 cx = x; cx < x2; ++cx) {
            g_gfx.framebuffer[row + cx] = color;
        }
    }
}

static inline void gfx_draw_rect_outline(INT32 x, INT32 y, INT32 w, INT32 h, UINT32 color, INT32 thickness) {
    gfx_draw_rect(x, y, w, thickness, color);                 // Top
    gfx_draw_rect(x, y + h - thickness, w, thickness, color); // Bottom
    gfx_draw_rect(x, y, thickness, h, color);                 // Left
    gfx_draw_rect(x + w - thickness, y, thickness, h, color); // Right
}

static inline void gfx_draw_char(CHAR8 c, INT32 x, INT32 y, UINT32 color, INT32 scale) {
    if (!g_gfx.framebuffer) return;
    const UINT8 *glyph = get_glyph(c);
    for (INT32 row = 0; row < 16; ++row) {
        UINT8 row_bits = glyph[row];
        for (INT32 col = 0; col < 8; ++col) {
            if ((row_bits >> (7 - col)) & 1) {
                if (scale == 1) {
                    gfx_put_pixel(x + col, y + row, color);
                } else {
                    gfx_draw_rect(x + col * scale, y + row * scale, scale, scale, color);
                }
            }
        }
    }
}

static inline void gfx_draw_string(const CHAR8 *str, INT32 x, INT32 y, UINT32 color, INT32 scale) {
    if (!str || !g_gfx.framebuffer) return;
    INT32 cursor_x = x;
    while (*str) {
        if (*str == '\n') {
            y += 18 * scale;
            cursor_x = x;
        } else {
            gfx_draw_char(*str, cursor_x, y, color, scale);
            cursor_x += 9 * scale;
        }
        str++;
    }
}

static inline void gfx_draw_panel(INT32 x, INT32 y, INT32 w, INT32 h, const CHAR8 *title, UINT32 bg_color, UINT32 border_color) {
    // Fondo de tarjeta
    gfx_draw_rect(x, y, w, h, bg_color);
    gfx_draw_rect_outline(x, y, w, h, border_color, 2);

    // Barra de titulo
    if (title) {
        gfx_draw_rect(x, y, w, 28, border_color);
        gfx_draw_string(title, x + 12, y + 6, COLOR_BG, 1);
    }
}

static inline void gfx_draw_progress_bar(INT32 x, INT32 y, INT32 w, INT32 h, INT32 percent, UINT32 bar_color, UINT32 bg_color) {
    if (percent < 0) percent = 0;
    if (percent > 100) percent = 100;
    gfx_draw_rect(x, y, w, h, bg_color);
    gfx_draw_rect_outline(x, y, w, h, COLOR_BORDER, 1);
    INT32 fill_w = ((w - 4) * percent) / 100;
    if (fill_w > 0) {
        gfx_draw_rect(x + 2, y + 2, fill_w, h - 4, bar_color);
    }
}

#endif /* EINSOF_GFX_H */
