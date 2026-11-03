      * Auto-generado por EinsofOS Polyglot Exporter para balance_contable_cierre
      * Tarea: Liquidacion de haberes contable financiera y calculo de saldos -> Lenguaje optimo: COBOL (Precision decimal fija exacta)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BALANCE_CONTABLE_CIERRE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SALDO-INICIAL       PIC 9(10)V99 COMP-3 VALUE 15000.50.
       01  GASTO-HARDWARE      PIC 9(10)V99 COMP-3 VALUE 123.45.
       01  SALDO-EXACTO        PIC 9(10)V99 COMP-3.
       PROCEDURE DIVISION.
           SUBTRACT GASTO-HARDWARE FROM SALDO-INICIAL GIVING SALDO-EXACTO.
           DISPLAY "SALDO EXACTO COBOL CALCULADO: " SALDO-EXACTO.
           STOP RUN.
