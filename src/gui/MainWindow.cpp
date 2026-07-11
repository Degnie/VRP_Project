// ============================================================================
//  MainWindow.cpp
// ============================================================================
#include "MainWindow.h"
#include "RouteView.h"

#include "../io/LectorInstancia.h"
#include "../algorithms/GreedyNN.h"
#include "../algorithms/SimulatedAnnealing.h"

#include <QAction>
#include <QApplication>
#include <QFileDialog>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QLabel>
#include <QLineEdit>
#include <QMenuBar>
#include <QMessageBox>
#include <QPushButton>
#include <QSplitter>
#include <QStatusBar>
#include <QTableWidget>
#include <QTextEdit>
#include <QToolBar>
#include <QVBoxLayout>
#include <QtConcurrent/QtConcurrent>

#include <algorithm>
#include <chrono>
#include <stdexcept>

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent)
    , m_tablaClientes(nullptr)
    , m_mapa(nullptr)
    , m_panelResultados(nullptr)
    , m_editX(nullptr)
    , m_editY(nullptr)
    , m_editDemanda(nullptr)
    , m_editCapacidad(nullptr)
    , m_lblResumen(nullptr)
{
    setWindowTitle("VRP Solver — Greedy vs Simulated Annealing");
    resize(1200, 750);
    construirInterfaz();
    connect(&m_watcher, &QFutureWatcher<std::vector<ResultadoAlgoritmo>>::finished,
            this, &MainWindow::onCalculoTerminado);
    statusBar()->showMessage("Listo. Carga una instancia o agrega clientes manualmente.");
}

// -----------------------------------------------------------------------------
//  Construcción de la interfaz
// -----------------------------------------------------------------------------
void MainWindow::construirInterfaz() {

    // ---------- Menú ----------
    QMenu* menuArchivo = menuBar()->addMenu("&Archivo");
    QAction* actCargar = menuArchivo->addAction("Cargar instancia...");
    QAction* actSalir  = menuArchivo->addAction("Salir");
    connect(actCargar, &QAction::triggered, this, &MainWindow::onCargarInstancia);
    connect(actSalir,  &QAction::triggered, qApp,  &QApplication::quit);

    QMenu* menuAlg = menuBar()->addMenu("&Algoritmos");
    QAction* actG  = menuAlg->addAction("Ejecutar Greedy");
    QAction* actSA = menuAlg->addAction("Ejecutar Simulated Annealing");
    QAction* actC  = menuAlg->addAction("Comparar ambos");
    connect(actG,  &QAction::triggered, this, &MainWindow::onEjecutarGreedy);
    connect(actSA, &QAction::triggered, this, &MainWindow::onEjecutarSA);
    connect(actC,  &QAction::triggered, this, &MainWindow::onCompararAlgoritmos);

    // ---------- Panel izquierdo ----------
    QWidget* panelIzq = new QWidget(this);
    QVBoxLayout* layIzq = new QVBoxLayout(panelIzq);

    // Grupo: capacidad del vehículo.
    QGroupBox* boxCap = new QGroupBox("Capacidad del vehículo (Q)", panelIzq);
    QHBoxLayout* layCap = new QHBoxLayout(boxCap);
    m_editCapacidad = new QLineEdit("40", boxCap);
    QPushButton* btnFijarCap = new QPushButton("Fijar", boxCap);
    layCap->addWidget(m_editCapacidad);
    layCap->addWidget(btnFijarCap);
    connect(btnFijarCap, &QPushButton::clicked, this, [this]() {
        bool ok = false;
        int q = m_editCapacidad->text().toInt(&ok);
        if (ok && q > 0) {
            m_instancia.setCapacidad(q);
            log(QString("Capacidad fijada en Q = %1").arg(q));
        } else {
            QMessageBox::warning(this, "Capacidad", "Ingresa un entero positivo.");
        }
    });

    // Grupo: agregar cliente manualmente.
    QGroupBox* boxNuevo = new QGroupBox("Agregar cliente", panelIzq);
    QVBoxLayout* layNuevo = new QVBoxLayout(boxNuevo);

    QHBoxLayout* layCampos = new QHBoxLayout();
    m_editX       = new QLineEdit(boxNuevo);   m_editX->setPlaceholderText("X");
    m_editY       = new QLineEdit(boxNuevo);   m_editY->setPlaceholderText("Y");
    m_editDemanda = new QLineEdit(boxNuevo);   m_editDemanda->setPlaceholderText("Demanda");
    layCampos->addWidget(m_editX);
    layCampos->addWidget(m_editY);
    layCampos->addWidget(m_editDemanda);

    QPushButton* btnAgregar = new QPushButton("Agregar", boxNuevo);
    connect(btnAgregar, &QPushButton::clicked, this, &MainWindow::onAgregarCliente);
    layNuevo->addLayout(layCampos);
    layNuevo->addWidget(btnAgregar);

    // Tabla de clientes.
    m_tablaClientes = new QTableWidget(panelIzq);
    m_tablaClientes->setColumnCount(4);
    m_tablaClientes->setHorizontalHeaderLabels(QStringList() << "ID" << "X" << "Y" << "Demanda");
    m_tablaClientes->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    m_tablaClientes->setEditTriggers(QAbstractItemView::NoEditTriggers);

    // Botones de acción.
    QPushButton* btnLimpiar     = new QPushButton("Limpiar todo",       panelIzq);
    QPushButton* btnCargar      = new QPushButton("Cargar archivo...",  panelIzq);
    QPushButton* btnGreedy      = new QPushButton("Ejecutar Greedy",    panelIzq);
    QPushButton* btnSA          = new QPushButton("Ejecutar SA",        panelIzq);
    QPushButton* btnComparar    = new QPushButton("Comparar ambos",     panelIzq);
    connect(btnLimpiar,  &QPushButton::clicked, this, &MainWindow::onLimpiar);
    connect(btnCargar,   &QPushButton::clicked, this, &MainWindow::onCargarInstancia);
    connect(btnGreedy,   &QPushButton::clicked, this, &MainWindow::onEjecutarGreedy);
    connect(btnSA,       &QPushButton::clicked, this, &MainWindow::onEjecutarSA);
    connect(btnComparar, &QPushButton::clicked, this, &MainWindow::onCompararAlgoritmos);

    layIzq->addWidget(boxCap);
    layIzq->addWidget(boxNuevo);
    layIzq->addWidget(m_tablaClientes, 1);
    layIzq->addWidget(btnCargar);
    layIzq->addWidget(btnLimpiar);
    layIzq->addWidget(btnGreedy);
    layIzq->addWidget(btnSA);
    layIzq->addWidget(btnComparar);

    // ---------- Panel central: mapa ----------
    m_mapa = new RouteView(this);

    // ---------- Panel inferior: resumen + log ----------
    QWidget* panelInf = new QWidget(this);
    QVBoxLayout* layInf = new QVBoxLayout(panelInf);
    m_lblResumen = new QLabel("Aún no hay solución.", panelInf);
    m_lblResumen->setStyleSheet("font-weight: bold; padding: 4px;");
    m_panelResultados = new QTextEdit(panelInf);
    m_panelResultados->setReadOnly(true);
    m_panelResultados->setFixedHeight(160);
    layInf->addWidget(m_lblResumen);
    layInf->addWidget(m_panelResultados);

    // ---------- Ensamblado con splitters ----------
    QSplitter* splitH = new QSplitter(Qt::Horizontal, this);
    splitH->addWidget(panelIzq);
    splitH->addWidget(m_mapa);
    splitH->setStretchFactor(0, 0);
    splitH->setStretchFactor(1, 1);
    splitH->setSizes(QList<int>() << 320 << 880);

    QSplitter* splitV = new QSplitter(Qt::Vertical, this);
    splitV->addWidget(splitH);
    splitV->addWidget(panelInf);
    splitV->setStretchFactor(0, 1);
    splitV->setStretchFactor(1, 0);

    setCentralWidget(splitV);

    // Fijamos una capacidad inicial y agregamos el depósito (0,0) automáticamente.
    m_instancia.setCapacidad(40);
    if (m_instancia.cantidadNodos() == 0) {
        m_instancia.agregarNodo(Cliente(0, 50.0, 50.0, 0));
        refrescarTabla();
    }
}

// -----------------------------------------------------------------------------
//  Slots
// -----------------------------------------------------------------------------
void MainWindow::onCargarInstancia() {
    QString rutaQt = QFileDialog::getOpenFileName(
        this, "Cargar instancia VRP", QString(),
        "Archivos VRP (*.vrp *.txt);;Todos (*)");
    if (rutaQt.isEmpty()) return;

    std::string error;
    Instancia   tmp;
    if (!LectorInstancia::cargar(rutaQt.toStdString(), tmp, error)) {
        QMessageBox::critical(this, "Error", QString::fromStdString(error));
        return;
    }
    m_instancia = tmp;
    m_solucion.limpiar();

    m_editCapacidad->setText(QString::number(m_instancia.capacidad()));
    refrescarTabla();
    m_mapa->mostrar(m_instancia, m_solucion);
    log(QString("Instancia cargada: %1 (n = %2, Q = %3)")
        .arg(QString::fromStdString(m_instancia.nombre()))
        .arg(m_instancia.cantidadClientes())
        .arg(m_instancia.capacidad()));
}

void MainWindow::onAgregarCliente() {
    bool okX = false, okY = false, okD = false;
    double x = m_editX->text().toDouble(&okX);
    double y = m_editY->text().toDouble(&okY);
    int    d = m_editDemanda->text().toInt(&okD);
    if (!okX || !okY || !okD || d <= 0) {
        QMessageBox::warning(this, "Datos inválidos",
            "Ingresa coordenadas numéricas y una demanda entera positiva.");
        return;
    }

    // El id del nuevo cliente es simplemente el siguiente disponible.
    int nuevoId = m_instancia.cantidadNodos();
    m_instancia.agregarNodo(Cliente(nuevoId, x, y, d));

    m_editX->clear(); m_editY->clear(); m_editDemanda->clear();
    refrescarTabla();
    m_mapa->mostrar(m_instancia, m_solucion);
    log(QString("Cliente %1 agregado en (%2, %3), demanda = %4")
        .arg(nuevoId).arg(x).arg(y).arg(d));
}

void MainWindow::onLimpiar() {
    m_instancia.limpiar();
    m_instancia.setCapacidad(m_editCapacidad->text().toInt());
    m_instancia.agregarNodo(Cliente(0, 50.0, 50.0, 0));   // depósito por defecto
    m_solucion.limpiar();
    refrescarTabla();
    m_mapa->limpiar();
    m_lblResumen->setText("Aún no hay solución.");
    log("Todo limpio. Solo queda el depósito.");
}

// Corre 'alg' sobre 'inst' midiendo tiempo, y atrapa cualquier excepción
// (p.ej. GreedyNN::resolver ante una demanda > Q) para que un dato de entrada
// hostil no tumbe el hilo de fondo.
template <typename Alg>
static ResultadoAlgoritmo correr(const QString& etiqueta, const Instancia& inst) {
    ResultadoAlgoritmo r;
    r.etiqueta = etiqueta;
    Alg alg;
    r.nombreAlgoritmo = QString::fromStdString(alg.nombre());
    using namespace std::chrono;
    try {
        auto t0 = high_resolution_clock::now();
        r.solucion = alg.resolver(inst);
        auto t1 = high_resolution_clock::now();
        r.ms = duration<double, std::milli>(t1 - t0).count();
    } catch (const std::exception& e) {
        r.error = QString::fromStdString(e.what());
    }
    return r;
}

void MainWindow::onEjecutarGreedy() {
    if (m_instancia.cantidadClientes() == 0) {
        QMessageBox::information(this, "Sin clientes", "Agrega o carga clientes primero.");
        return;
    }
    ejecutarAsync([](Instancia inst) {
        return std::vector<ResultadoAlgoritmo>{ correr<GreedyNN>("GREEDY", inst) };
    });
}

void MainWindow::onEjecutarSA() {
    if (m_instancia.cantidadClientes() == 0) {
        QMessageBox::information(this, "Sin clientes", "Agrega o carga clientes primero.");
        return;
    }
    ejecutarAsync([](Instancia inst) {
        return std::vector<ResultadoAlgoritmo>{ correr<SimulatedAnnealing>("SA", inst) };
    });
}

void MainWindow::onCompararAlgoritmos() {
    if (m_instancia.cantidadClientes() == 0) {
        QMessageBox::information(this, "Sin clientes", "Agrega o carga clientes primero.");
        return;
    }
    ejecutarAsync([](Instancia inst) {
        return std::vector<ResultadoAlgoritmo>{
            correr<GreedyNN>("GREEDY", inst),
            correr<SimulatedAnnealing>("SA", inst)
        };
    });
}

// -----------------------------------------------------------------------------
//  Helpers privados
// -----------------------------------------------------------------------------
void MainWindow::ejecutarAsync(std::function<std::vector<ResultadoAlgoritmo>(Instancia)> trabajo) {
    if (m_ejecutando) {
        statusBar()->showMessage("Ya hay un cálculo en curso, espera a que termine.");
        return;
    }
    m_ejecutando = true;
    statusBar()->showMessage("Calculando...");

    // Copiamos la instancia: el hilo de fondo trabaja sobre su propia copia,
    // así el usuario puede seguir usando la GUI sin pisar m_instancia.
    Instancia copia = m_instancia;
    QFuture<std::vector<ResultadoAlgoritmo>> future =
        QtConcurrent::run([trabajo, copia]() { return trabajo(copia); });
    m_watcher.setFuture(future);
}

void MainWindow::onCalculoTerminado() {
    m_ejecutando = false;
    statusBar()->showMessage("Listo.");

    std::vector<ResultadoAlgoritmo> resultados = m_watcher.result();

    for (const ResultadoAlgoritmo& r : resultados) {
        if (!r.error.isEmpty()) {
            QMessageBox::critical(this, "Error al resolver",
                QString("[%1] %2").arg(r.etiqueta, r.error));
        }
    }
    resultados.erase(std::remove_if(resultados.begin(), resultados.end(),
        [](const ResultadoAlgoritmo& r) { return !r.error.isEmpty(); }), resultados.end());
    if (resultados.empty()) return;

    if (resultados.size() == 1) {
        const ResultadoAlgoritmo& r = resultados[0];
        double cost = r.solucion.costoTotal(m_instancia);
        m_solucion = r.solucion;
        refrescarMapa(r.solucion);

        QString linea = QString("[%1] %2  |  costo = %3  |  tiempo = %4 ms  |  rutas = %5  |  válida = %6")
            .arg(r.etiqueta, r.nombreAlgoritmo)
            .arg(cost, 0, 'f', 2)
            .arg(r.ms,  0, 'f', 2)
            .arg(r.solucion.cantidadRutas())
            .arg(r.solucion.esValida(m_instancia) ? "SI" : "NO");
        log(linea);
        m_lblResumen->setText(linea);
        return;
    }

    // Comparación (Greedy vs SA).
    const ResultadoAlgoritmo& rg = resultados[0];
    const ResultadoAlgoritmo& rsa = resultados[1];
    double costG  = rg.solucion.costoTotal(m_instancia);
    double costSA = rsa.solucion.costoTotal(m_instancia);

    Solucion mejor = (costSA < costG) ? rsa.solucion : rg.solucion;
    QString  cual  = (costSA < costG) ? "SA" : "Greedy";
    m_solucion = mejor;
    refrescarMapa(mejor);

    double mejora = (costG - costSA) / costG * 100.0;

    log("======= COMPARACION =======");
    log(QString("Greedy:  costo = %1  |  tiempo = %2 ms  |  rutas = %3")
        .arg(costG, 0, 'f', 2).arg(rg.ms, 0, 'f', 2).arg(rg.solucion.cantidadRutas()));
    log(QString("SA:      costo = %1  |  tiempo = %2 ms  |  rutas = %3")
        .arg(costSA, 0, 'f', 2).arg(rsa.ms, 0, 'f', 2).arg(rsa.solucion.cantidadRutas()));
    log(QString("Mejora del SA sobre Greedy: %1 %%").arg(mejora, 0, 'f', 2));
    log(QString("Mostrando en el mapa la mejor solución (%1).").arg(cual));

    m_lblResumen->setText(
        QString("COMPARACION → Greedy: %1  |  SA: %2  |  Mejora SA: %3 %%")
        .arg(costG, 0, 'f', 2).arg(costSA, 0, 'f', 2).arg(mejora, 0, 'f', 2));
}

void MainWindow::refrescarTabla() {
    m_tablaClientes->setRowCount(m_instancia.cantidadNodos());
    for (int i = 0; i < m_instancia.cantidadNodos(); ++i) {
        const Cliente& c = m_instancia.nodo(i);
        m_tablaClientes->setItem(i, 0, new QTableWidgetItem(QString::number(c.id)));
        m_tablaClientes->setItem(i, 1, new QTableWidgetItem(QString::number(c.x, 'f', 2)));
        m_tablaClientes->setItem(i, 2, new QTableWidgetItem(QString::number(c.y, 'f', 2)));
        m_tablaClientes->setItem(i, 3, new QTableWidgetItem(
            i == 0 ? QString("Depósito") : QString::number(c.demanda)));
    }
}

void MainWindow::refrescarMapa(const Solucion& sol) {
    // La instancia no cambió (solo la solución), así que reusamos el
    // bounding box ya calculado en vez de recorrer las coordenadas de nuevo.
    m_mapa->mostrarSolucion(sol);
}

void MainWindow::log(const QString& linea) {
    m_panelResultados->append(linea);
}
