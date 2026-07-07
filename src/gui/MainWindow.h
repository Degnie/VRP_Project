// ============================================================================
//  MainWindow.h
//  ----------------------------------------------------------------------------
//  Ventana principal de la aplicación.
//
//  Layout:
//    +--------------------------------------------------+
//    | [ Barra de botones ]                             |
//    +-----------+--------------------------------------+
//    | Tabla de  |                                      |
//    | clientes  |          Mapa de rutas               |
//    |           |          (RouteView)                 |
//    | (izq.)    |                                      |
//    +-----------+--------------------------------------+
//    | Panel de resultados / comparación                |
//    +--------------------------------------------------+
// ============================================================================
#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include "../core/Instancia.h"
#include "../core/Solucion.h"

// Declaraciones adelantadas (no hace falta incluir cada header aquí).
class QTableWidget;
class QTextEdit;
class QLabel;
class QLineEdit;
class RouteView;

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget* parent = nullptr);

private slots:
    // Acciones de los botones y menús.
    void onCargarInstancia();
    void onAgregarCliente();
    void onLimpiar();
    void onEjecutarGreedy();
    void onEjecutarSA();
    void onCompararAlgoritmos();

private:
    // Construcción de la interfaz (llamada desde el constructor).
    void construirInterfaz();

    // Repinta la tabla y el mapa con los datos actuales.
    void refrescarTabla();
    void refrescarMapa(const Solucion& sol);

    // Escribe una línea en el panel de resultados.
    void log(const QString& linea);

    // Ejecuta un algoritmo y devuelve tiempo (ms) y solución obtenida.
    void ejecutarYMostrar(const QString& etiqueta,
                          class IVRPSolver* solver);

    // Datos del problema y última solución.
    Instancia m_instancia;
    Solucion  m_solucion;

    // Widgets principales.
    QTableWidget* m_tablaClientes;
    RouteView*    m_mapa;
    QTextEdit*    m_panelResultados;

    // Campos para agregar cliente manualmente.
    QLineEdit* m_editX;
    QLineEdit* m_editY;
    QLineEdit* m_editDemanda;
    QLineEdit* m_editCapacidad;

    // Etiquetas de resumen bajo el mapa.
    QLabel* m_lblResumen;
};

#endif // MAINWINDOW_H
