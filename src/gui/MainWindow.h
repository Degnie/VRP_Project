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
#include <QFutureWatcher>
#include <QString>
#include <functional>
#include <memory>
#include <vector>
#include "../core/Instancia.h"
#include "../core/Solucion.h"

// Declaraciones adelantadas (no hace falta incluir cada header aquí).
class QWidget;
class QTableWidget;
class QTextEdit;
class QLabel;
class QLineEdit;
class RouteView;

// Resultado de correr UN algoritmo (usado tanto para una corrida simple
// como para cada rama de "Comparar ambos"). Si algo sale mal (p.ej. una
// instancia con demanda > Q), 'error' queda con el mensaje y 'solucion' vacía.
struct ResultadoAlgoritmo {
    QString  etiqueta;
    QString  nombreAlgoritmo;
    Solucion solucion;
    double   ms = 0.0;
    QString  error;
};

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

    // Se dispara en el hilo de la UI cuando el cálculo en background termina.
    void onCalculoTerminado();

private:
    // Construcción de la interfaz (llamada desde el constructor).
    void construirInterfaz();

    // Repinta la tabla y el mapa con los datos actuales.
    void refrescarTabla();
    void refrescarMapa(const Solucion& sol);

    // Escribe una línea en el panel de resultados.
    void log(const QString& linea);

    // Lanza 'trabajo' en un hilo secundario (QtConcurrent) y programa
    // onCalculoTerminado() para que corra en el hilo de la UI cuando termine.
    // 'trabajo' recibe la instancia por referencia const sobre un snapshot
    // (shared_ptr<const Instancia>) tomado una sola vez al lanzar: el hilo
    // de fondo nunca toca m_instancia/m_solucion directamente, y capturar
    // el puntero en la lambda no vuelve a copiar los datos.
    void ejecutarAsync(std::function<std::vector<ResultadoAlgoritmo>(const Instancia&)> trabajo);

    // Datos del problema y última solución. Solo se leen/escriben desde el
    // hilo de la UI (el hilo de fondo trabaja sobre su propio snapshot).
    Instancia m_instancia;
    Solucion  m_solucion;

    QFutureWatcher<std::vector<ResultadoAlgoritmo>> m_watcher;
    bool m_ejecutando = false;

    // Widgets principales.
    QWidget*      m_panelIzq;   // se deshabilita mientras corre un cálculo
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
