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
#include <QEvent>
#include <QFile>
#include <QFileDialog>
#include <QGridLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QIcon>
#include <QLabel>
#include <QLineEdit>
#include <QMenuBar>
#include <QMessageBox>
#include <QProgressBar>
#include <QPushButton>
#include <QResizeEvent>
#include <QSplitter>
#include <QStatusBar>
#include <QTabWidget>
#include <QTableView>
#include <QTextEdit>
#include <QToolBar>
#include <QVBoxLayout>
#include <QtConcurrent/QtConcurrent>

#include <algorithm>
#include <chrono>
#include <memory>
#include <stdexcept>

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent)
    , m_panelIzq(nullptr)
    , m_tablaClientes(nullptr)
    , m_modeloClientes(nullptr)
    , m_mapa(nullptr)
    , m_panelResultados(nullptr)
    , m_progreso(nullptr)
    , m_editX(nullptr)
    , m_editY(nullptr)
    , m_editDemanda(nullptr)
    , m_editCapacidad(nullptr)
    , m_lblResumen(nullptr)
{
    setWindowTitle("VRP Solver — Greedy vs Simulated Annealing");
    resize(1200, 750);

    // QSS embebido vía recurso Qt (resources/style.qss, compilado con AUTORCC).
    QFile hojaEstilos(":/style.qss");
    if (hojaEstilos.open(QIODevice::ReadOnly | QIODevice::Text)) {
        setStyleSheet(QString::fromUtf8(hojaEstilos.readAll()));
    }

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

    // ---------- Panel izquierdo: pestañas ----------
    QTabWidget* tabs = new QTabWidget(this);
    m_panelIzq = tabs;   // se deshabilita como bloque durante un cálculo

    // ===== Pestaña 1: Datos y Configuración =====
    QWidget* tabDatos = new QWidget(tabs);
    QVBoxLayout* layDatos = new QVBoxLayout(tabDatos);

    // Grupo: capacidad del vehículo.
    QGroupBox* boxCap = new QGroupBox("Capacidad del vehículo (Q)", tabDatos);
    QHBoxLayout* layCap = new QHBoxLayout(boxCap);
    QLabel* lblCap = new QLabel("Q:", boxCap);
    m_editCapacidad = new QLineEdit("40", boxCap);
    lblCap->setBuddy(m_editCapacidad);
    m_editCapacidad->setAccessibleName("Capacidad del vehículo");
    QPushButton* btnFijarCap = new QPushButton("Fijar", boxCap);
    layCap->addWidget(lblCap);
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

    // Grupo: agregar cliente manualmente. Cada campo con su QLabel-buddy
    // (clic en la etiqueta enfoca el campo) y un nombre accesible para
    // lectores de pantalla — los placeholders solos no alcanzan para WCAG.
    QGroupBox* boxNuevo = new QGroupBox("Agregar cliente", tabDatos);
    QVBoxLayout* layNuevo = new QVBoxLayout(boxNuevo);

    QGridLayout* layCampos = new QGridLayout();
    QLabel* lblX = new QLabel("X:", boxNuevo);
    QLabel* lblY = new QLabel("Y:", boxNuevo);
    QLabel* lblD = new QLabel("Demanda:", boxNuevo);
    m_editX       = new QLineEdit(boxNuevo);
    m_editY       = new QLineEdit(boxNuevo);
    m_editDemanda = new QLineEdit(boxNuevo);
    lblX->setBuddy(m_editX);
    lblY->setBuddy(m_editY);
    lblD->setBuddy(m_editDemanda);
    m_editX->setAccessibleName("Coordenada X del nuevo cliente");
    m_editY->setAccessibleName("Coordenada Y del nuevo cliente");
    m_editDemanda->setAccessibleName("Demanda del nuevo cliente");
    layCampos->addWidget(lblX, 0, 0); layCampos->addWidget(m_editX, 0, 1);
    layCampos->addWidget(lblY, 0, 2); layCampos->addWidget(m_editY, 0, 3);
    layCampos->addWidget(lblD, 0, 4); layCampos->addWidget(m_editDemanda, 0, 5);

    QPushButton* btnAgregar = new QPushButton("Agregar", boxNuevo);
    connect(btnAgregar, &QPushButton::clicked, this, &MainWindow::onAgregarCliente);
    layNuevo->addLayout(layCampos);
    layNuevo->addWidget(btnAgregar);

    // Tabla de clientes: QTableView + modelo propio (ClientesTableModel),
    // en vez de QTableWidget con un QTableWidgetItem por celda — con
    // instancias de millones de clientes, la vista solo pide data() para
    // las celdas realmente visibles.
    m_modeloClientes = new ClientesTableModel(this);
    m_tablaClientes  = new QTableView(tabDatos);
    m_tablaClientes->setModel(m_modeloClientes);
    m_tablaClientes->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    m_tablaClientes->setEditTriggers(QAbstractItemView::NoEditTriggers);

    QPushButton* btnCargar  = new QPushButton(QIcon(":/icons/folder-open.svg"), "Cargar archivo...", tabDatos);
    QPushButton* btnLimpiar = new QPushButton(QIcon(":/icons/trash.svg"), "Limpiar todo", tabDatos);
    btnLimpiar->setObjectName("btnLimpiar");   // QSS: bajo peso visual (acción destructiva)
    connect(btnLimpiar, &QPushButton::clicked, this, &MainWindow::onLimpiar);
    connect(btnCargar,  &QPushButton::clicked, this, &MainWindow::onCargarInstancia);

    layDatos->addWidget(boxCap);
    layDatos->addWidget(boxNuevo);
    layDatos->addWidget(m_tablaClientes, 1);
    layDatos->addWidget(btnCargar);
    layDatos->addWidget(btnLimpiar);

    // ===== Pestaña 2: Simulación =====
    QWidget* tabSim = new QWidget(tabs);
    QVBoxLayout* laySim = new QVBoxLayout(tabSim);
    QLabel* lblAyuda = new QLabel(
        "Ejecuta un algoritmo sobre la instancia actual, o compara ambos "
        "para quedarte con la mejor solución.", tabSim);
    lblAyuda->setWordWrap(true);
    lblAyuda->setStyleSheet("color: #607D8B;");

    QPushButton* btnGreedy   = new QPushButton(QIcon(":/icons/play-greedy.svg"), "Ejecutar Greedy", tabSim);
    QPushButton* btnSA       = new QPushButton(QIcon(":/icons/play-sa.svg"), "Ejecutar Simulated Annealing", tabSim);
    QPushButton* btnComparar = new QPushButton(QIcon(":/icons/compare.svg"), "Comparar ambos", tabSim);
    btnComparar->setObjectName("btnComparar");   // QSS: acento esmeralda (CTA)
    connect(btnGreedy,   &QPushButton::clicked, this, &MainWindow::onEjecutarGreedy);
    connect(btnSA,       &QPushButton::clicked, this, &MainWindow::onEjecutarSA);
    connect(btnComparar, &QPushButton::clicked, this, &MainWindow::onCompararAlgoritmos);

    laySim->addWidget(lblAyuda);
    laySim->addWidget(btnGreedy);
    laySim->addWidget(btnSA);
    laySim->addWidget(btnComparar);
    laySim->addStretch(1);

    tabs->addTab(tabDatos, "Datos y Configuración");
    tabs->addTab(tabSim, "Simulación");

    // Orden de tabulación explícito: capacidad → agregar cliente → tabla →
    // cargar/limpiar (pestaña 1) y greedy → SA → comparar (pestaña 2).
    setTabOrder(m_editCapacidad, btnFijarCap);
    setTabOrder(btnFijarCap, m_editX);
    setTabOrder(m_editX, m_editY);
    setTabOrder(m_editY, m_editDemanda);
    setTabOrder(m_editDemanda, btnAgregar);
    setTabOrder(btnAgregar, m_tablaClientes);
    setTabOrder(m_tablaClientes, btnCargar);
    setTabOrder(btnCargar, btnLimpiar);
    setTabOrder(btnGreedy, btnSA);
    setTabOrder(btnSA, btnComparar);

    // ---------- Panel central: mapa ----------
    m_mapa = new RouteView(this);

    // Overlay de progreso: hijo directo de m_mapa (no del layout), para
    // flotar SOBRE el mapa en vez de ocupar espacio propio. Se reposiciona
    // en cada resize de m_mapa vía eventFilter.
    m_progreso = new QProgressBar(m_mapa);
    m_progreso->setRange(0, 0);   // indeterminado
    m_progreso->setTextVisible(false);
    m_progreso->setFixedHeight(4);
    m_progreso->hide();
    m_mapa->installEventFilter(this);

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
    splitH->addWidget(m_panelIzq);
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
//  Overlay de progreso: sigue el tamaño de m_mapa (es su hijo directo, no
//  vive en un layout, así que hay que reposicionarlo a mano).
// -----------------------------------------------------------------------------
bool MainWindow::eventFilter(QObject* watched, QEvent* event) {
    if (watched == m_mapa && event->type() == QEvent::Resize) {
        auto* re = static_cast<QResizeEvent*>(event);
        m_progreso->setGeometry(0, 0, re->size().width(), 4);
    }
    return QMainWindow::eventFilter(watched, event);
}

// -----------------------------------------------------------------------------
//  Slots
// -----------------------------------------------------------------------------
void MainWindow::onCargarInstancia() {
    // DEFAULT_DATA_DIR viene de CMake (target_compile_definitions): abre el
    // diálogo directo en la carpeta data/ del proyecto en vez de a ciegas.
    QString rutaQt = QFileDialog::getOpenFileName(
        this, "Cargar instancia VRP", QString(DEFAULT_DATA_DIR),
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
    ejecutarAsync([](const Instancia& inst) {
        return std::vector<ResultadoAlgoritmo>{ correr<GreedyNN>("GREEDY", inst) };
    });
}

void MainWindow::onEjecutarSA() {
    if (m_instancia.cantidadClientes() == 0) {
        QMessageBox::information(this, "Sin clientes", "Agrega o carga clientes primero.");
        return;
    }
    ejecutarAsync([](const Instancia& inst) {
        return std::vector<ResultadoAlgoritmo>{ correr<SimulatedAnnealing>("SA", inst) };
    });
}

void MainWindow::onCompararAlgoritmos() {
    if (m_instancia.cantidadClientes() == 0) {
        QMessageBox::information(this, "Sin clientes", "Agrega o carga clientes primero.");
        return;
    }
    ejecutarAsync([](const Instancia& inst) {
        return std::vector<ResultadoAlgoritmo>{
            correr<GreedyNN>("GREEDY", inst),
            correr<SimulatedAnnealing>("SA", inst)
        };
    });
}

// -----------------------------------------------------------------------------
//  Helpers privados
// -----------------------------------------------------------------------------

// Busca un resultado por su etiqueta ("GREEDY"/"SA") en vez de asumir un
// índice fijo — más robusto si el orden de 'resultados' cambia. No-const
// para poder std::move() la solución ganadora fuera de 'resultados'.
static ResultadoAlgoritmo* buscarPorEtiqueta(
    std::vector<ResultadoAlgoritmo>& resultados, const QString& etiqueta) {
    for (ResultadoAlgoritmo& r : resultados) {
        if (r.etiqueta == etiqueta) return &r;
    }
    return nullptr;
}

void MainWindow::ejecutarAsync(std::function<std::vector<ResultadoAlgoritmo>(const Instancia&)> trabajo) {
    if (m_ejecutando) {
        statusBar()->showMessage("Ya hay un cálculo en curso, espera a que termine.");
        return;
    }
    m_ejecutando = true;
    // Bloqueamos todo lo que puede mutar m_instancia mientras el hilo de
    // fondo trabaja sobre su snapshot: si el usuario agregara un cliente o
    // cargara otra instancia a mitad de cálculo, el resultado terminaría
    // evaluado (costoTotal/esValida) contra una instancia distinta a la que
    // el solver realmente resolvió.
    m_panelIzq->setEnabled(false);
    menuBar()->setEnabled(false);
    statusBar()->showMessage("Calculando...");
    m_progreso->raise();
    m_progreso->show();

    // Snapshot tomado una sola vez; el shared_ptr se captura por copia en la
    // lambda (copia de puntero, no de los datos) así que QtConcurrent::run
    // no vuelve a duplicar la instancia al empaquetar la tarea.
    auto snapshot = std::make_shared<const Instancia>(m_instancia);
    QFuture<std::vector<ResultadoAlgoritmo>> future =
        QtConcurrent::run([trabajo, snapshot]() { return trabajo(*snapshot); });
    m_watcher.setFuture(future);
}

void MainWindow::onCalculoTerminado() {
    m_ejecutando = false;
    m_panelIzq->setEnabled(true);
    menuBar()->setEnabled(true);
    m_progreso->hide();
    statusBar()->showMessage("Listo.");

    std::vector<ResultadoAlgoritmo> resultados = m_watcher.result();

    for (const ResultadoAlgoritmo& r : resultados) {
        if (!r.error.isEmpty()) {
            QMessageBox::critical(this, "Error al resolver",
                QString("[%1] %2").arg(r.etiqueta, r.error));
            log(QString("[%1] Error: %2").arg(r.etiqueta, r.error.toHtmlEscaped()));
        }
    }
    resultados.erase(std::remove_if(resultados.begin(), resultados.end(),
        [](const ResultadoAlgoritmo& r) { return !r.error.isEmpty(); }), resultados.end());

    if (resultados.empty()) {
        // Todo lo que llegó falló: no dejamos pintada en el mapa la
        // solución "fantasma" de un cómputo anterior — se limpia la vista.
        m_solucion.limpiar();
        m_mapa->limpiar();
        m_lblResumen->setText("Sin solución (el último cálculo falló).");
        return;
    }

    if (resultados.size() == 1) {
        ResultadoAlgoritmo& r = resultados[0];
        // Calculamos todo lo que necesitamos ANTES de mover r.solucion:
        // después del move, r.solucion queda en un estado válido pero
        // no-especificado (probablemente vacío).
        double cost   = r.solucion.costoTotal(m_instancia);
        bool   valida = r.solucion.esValida(m_instancia);
        int    rutas  = r.solucion.cantidadRutas();

        // Traslada el vector de rutas a m_solucion sin copiarlo (r.solucion
        // vive en un std::vector local a esta función, no hace falta
        // conservarlo después de esto).
        m_solucion = std::move(r.solucion);
        refrescarMapa(m_solucion);

        QString linea = QString("[%1] %2  |  costo = %3  |  tiempo = %4 ms  |  rutas = %5  |  válida = %6")
            .arg(r.etiqueta, r.nombreAlgoritmo)
            .arg(cost, 0, 'f', 2)
            .arg(r.ms,  0, 'f', 2)
            .arg(rutas)
            .arg(valida ? "SI" : "NO");
        log(linea);
        m_lblResumen->setText(linea);
        return;
    }

    // Comparación (Greedy vs SA), buscadas por etiqueta.
    ResultadoAlgoritmo* pg  = buscarPorEtiqueta(resultados, "GREEDY");
    ResultadoAlgoritmo* psa = buscarPorEtiqueta(resultados, "SA");
    if (!pg || !psa) return;   // no debería pasar, pero evita un [] fuera de rango
    double costG  = pg->solucion.costoTotal(m_instancia);
    double costSA = psa->solucion.costoTotal(m_instancia);
    bool   saGana = costSA < costG;
    QString cual  = saGana ? "SA" : "Greedy";
    int rutasG    = pg->solucion.cantidadRutas();
    int rutasSA   = psa->solucion.cantidadRutas();

    // Solo movemos la ganadora (la otra se descarta junto con 'resultados').
    m_solucion = saGana ? std::move(psa->solucion) : std::move(pg->solucion);
    refrescarMapa(m_solucion);

    double mejora = (costG - costSA) / costG * 100.0;

    log("======= COMPARACION =======");
    log(QString("Greedy:  costo = %1  |  tiempo = %2 ms  |  rutas = %3")
        .arg(costG, 0, 'f', 2).arg(pg->ms, 0, 'f', 2).arg(rutasG));
    log(QString("SA:      costo = %1  |  tiempo = %2 ms  |  rutas = %3")
        .arg(costSA, 0, 'f', 2).arg(psa->ms, 0, 'f', 2).arg(rutasSA));
    log(QString("Mejora del SA sobre Greedy: %1 %%").arg(mejora, 0, 'f', 2));
    log(QString("Mostrando en el mapa la mejor solución (%1).").arg(cual));

    m_lblResumen->setText(
        QString("COMPARACION → Greedy: %1  |  SA: %2  |  Mejora SA: %3 %%")
        .arg(costG, 0, 'f', 2).arg(costSA, 0, 'f', 2).arg(mejora, 0, 'f', 2));
}

void MainWindow::refrescarTabla() {
    // El modelo lee directo de m_instancia; esto solo dispara el reset
    // (begin/endResetModel) para que la vista vuelva a pedir las celdas
    // visibles. Nada de reconstruir items fila por fila.
    m_modeloClientes->setInstancia(&m_instancia);
}

void MainWindow::refrescarMapa(const Solucion& sol) {
    // La instancia no cambió (solo la solución), así que reusamos el
    // bounding box ya calculado en vez de recorrer las coordenadas de nuevo.
    m_mapa->mostrarSolucion(sol);
}

void MainWindow::log(const QString& linea) {
    // QTextEdit::append() ya interpreta HTML automáticamente si lo detecta
    // (Qt::mightBeRichText). Acá solo inyectamos badges para los patrones
    // conocidos que arma onCalculoTerminado() — el resto de las líneas pasa
    // sin tocar.
    QString formateada = linea;
    formateada.replace("válida = SI",
        "<span style=\"background:#00875A;color:white;border-radius:4px;"
        "padding:1px 6px;font-weight:600;\">&#10003; VÁLIDA</span>");
    formateada.replace("válida = NO",
        "<span style=\"background:#D55E00;color:white;border-radius:4px;"
        "padding:1px 6px;font-weight:600;\">&#10007; INVÁLIDA</span>");
    if (linea.startsWith("[") && linea.contains("] Error:")) {
        formateada = "<span style=\"background:#D55E00;color:white;border-radius:4px;"
                     "padding:1px 6px;font-weight:600;\">&#10007; ERROR</span> " + formateada;
    }
    m_panelResultados->append(formateada);
}
