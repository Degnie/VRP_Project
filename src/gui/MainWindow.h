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

#include <QAbstractTableModel>
#include <QMainWindow>
#include <QFutureWatcher>
#include <QString>
#include <QVariant>
#include <functional>
#include <memory>
#include <vector>
#include "../core/Instancia.h"
#include "../core/Solucion.h"

// Declaraciones adelantadas (no hace falta incluir cada header aquí).
class QWidget;
class QTableView;
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

// Modelo Qt para la tabla de clientes: lee directo de un const Instancia*
// y genera cada celda on-demand en data() — O(1) por celda, sin instanciar
// un QTableWidgetItem por fila/columna (con 10^6 clientes eso son millones
// de objetos QObject-like vivos en memoria a la vez, solo por la tabla).
class ClientesTableModel : public QAbstractTableModel {
    Q_OBJECT
public:
    explicit ClientesTableModel(QObject* parent = nullptr) : QAbstractTableModel(parent) {}

    // No es dueño de la instancia: apunta a m_instancia de MainWindow, que
    // vive mientras viva la ventana. Llamar de nuevo cada vez que cambian
    // los datos (carga, agregar cliente, limpiar) para refrescar la vista.
    void setInstancia(const Instancia* inst) {
        beginResetModel();
        m_instancia = inst;
        endResetModel();
    }

    int rowCount(const QModelIndex& = QModelIndex()) const override {
        return m_instancia ? m_instancia->cantidadNodos() : 0;
    }

    int columnCount(const QModelIndex& = QModelIndex()) const override { return 4; }

    QVariant data(const QModelIndex& index, int role) const override {
        if (!m_instancia || role != Qt::DisplayRole || !index.isValid()) return QVariant();
        const Cliente& c = m_instancia->nodo(index.row());
        switch (index.column()) {
            case 0: return c.id;
            case 1: return QString::number(c.x, 'f', 2);
            case 2: return QString::number(c.y, 'f', 2);
            case 3: return index.row() == 0 ? QString("Depósito") : QString::number(c.demanda);
            default: return QVariant();
        }
    }

    QVariant headerData(int section, Qt::Orientation orientation, int role) const override {
        if (role != Qt::DisplayRole || orientation != Qt::Horizontal) return QVariant();
        static const char* nombres[] = {"ID", "X", "Y", "Demanda"};
        if (section < 0 || section >= 4) return QVariant();
        return QString(nombres[section]);
    }

private:
    const Instancia* m_instancia = nullptr;
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
    QWidget*             m_panelIzq;   // se deshabilita mientras corre un cálculo
    QTableView*          m_tablaClientes;
    ClientesTableModel*  m_modeloClientes;
    RouteView*           m_mapa;
    QTextEdit*           m_panelResultados;

    // Campos para agregar cliente manualmente.
    QLineEdit* m_editX;
    QLineEdit* m_editY;
    QLineEdit* m_editDemanda;
    QLineEdit* m_editCapacidad;

    // Etiquetas de resumen bajo el mapa.
    QLabel* m_lblResumen;
};

#endif // MAINWINDOW_H
