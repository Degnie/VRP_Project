// ============================================================================
//  RouteView.cpp
// ============================================================================
#include "RouteView.h"

#include <QPen>
#include <QBrush>
#include <QGraphicsEllipseItem>
#include <QGraphicsLineItem>
#include <QGraphicsPathItem>
#include <QGraphicsSimpleTextItem>
#include <QPainterPath>
#include <algorithm>
#include <limits>

// Por encima de este tamaño, dejamos de crear un QGraphicsItem por nodo/
// segmento (miles de items individuales hacen que Qt se arrastre al
// repintar/hacer zoom) y pasamos a dibujar en lote con QPainterPath.
static const int LOD_UMBRAL_NODOS = 500;

RouteView::RouteView(QWidget* parent)
    : QGraphicsView(parent)
{
    m_escena = new QGraphicsScene(this);
    setScene(m_escena);
    setRenderHint(QPainter::Antialiasing, true);
    setBackgroundBrush(QBrush(QColor(250, 250, 250)));
}

void RouteView::limpiar() {
    m_escena->clear();
    m_bboxValido = false;
}

QColor RouteView::colorPorIndice(int i) const {
    // Paleta simple; se cicla si hay más rutas que colores.
    static const QColor paleta[] = {
        QColor(220,  50,  50),   // rojo
        QColor( 50, 120, 220),   // azul
        QColor( 40, 170,  80),   // verde
        QColor(230, 150,  30),   // naranja
        QColor(140,  60, 190),   // morado
        QColor( 30, 170, 180),   // turquesa
        QColor(200,  70, 150),   // rosa
        QColor(120, 100,  50),   // marrón
    };
    const int total = sizeof(paleta) / sizeof(paleta[0]);
    return paleta[i % total];
}

// Recorre las coordenadas UNA vez y fija el sceneRect. Solo se llama cuando
// la instancia cambió (mostrar()), no en cada repintado.
void RouteView::calcularBoundingBox() {
    m_xMin =  std::numeric_limits<double>::infinity();
    m_xMax = -std::numeric_limits<double>::infinity();
    m_yMin =  std::numeric_limits<double>::infinity();
    m_yMax = -std::numeric_limits<double>::infinity();

    for (int i = 0; i < m_instancia.cantidadNodos(); ++i) {
        const Cliente& c = m_instancia.nodo(i);
        if (c.x < m_xMin) m_xMin = c.x;
        if (c.x > m_xMax) m_xMax = c.x;
        if (c.y < m_yMin) m_yMin = c.y;
        if (c.y > m_yMax) m_yMax = c.y;
    }

    // Margen para que los puntos no se peguen al borde.
    double margen = 40.0;
    m_escena->setSceneRect(m_xMin - margen, m_yMin - margen,
                           (m_xMax - m_xMin) + 2 * margen,
                           (m_yMax - m_yMin) + 2 * margen);
    m_bboxValido = true;
}

void RouteView::mostrar(const Instancia& inst, const Solucion& sol) {
    m_instancia = inst;
    if (m_instancia.cantidadNodos() == 0) {
        m_escena->clear();
        m_bboxValido = false;
        return;
    }
    calcularBoundingBox();
    dibujar(sol);
}

void RouteView::mostrarSolucion(const Solucion& sol) {
    if (!m_bboxValido) return;   // no hay instancia cargada todavía
    dibujar(sol);
}

// Dibuja nodos + rutas usando el bounding box ya calculado (no recorre las
// coordenadas de nuevo).
void RouteView::dibujar(const Solucion& sol) {
    m_escena->clear();

    const bool lod = m_instancia.cantidadNodos() > LOD_UMBRAL_NODOS;

    // 1) Dibujar las rutas (líneas).
    if (!lod) {
        // Pocas rutas/nodos: un QGraphicsLineItem por segmento es legible
        // y permite estilos por-segmento sin complicarse.
        for (int r = 0; r < sol.cantidadRutas(); ++r) {
            const Ruta& ruta = sol.ruta(r);
            QPen pluma(colorPorIndice(r));
            pluma.setWidth(2);

            for (int k = 0; k + 1 < static_cast<int>(ruta.size()); ++k) {
                const Cliente& a = m_instancia.nodo(ruta[k]);
                const Cliente& b = m_instancia.nodo(ruta[k + 1]);
                m_escena->addLine(a.x, a.y, b.x, b.y, pluma);
            }
        }
    } else {
        // Muchos nodos: un QGraphicsPathItem por ruta (no por segmento) —
        // pasa de O(nodos_de_la_ruta) items a 1 solo item por ruta.
        for (int r = 0; r < sol.cantidadRutas(); ++r) {
            const Ruta& ruta = sol.ruta(r);
            if (ruta.empty()) continue;

            QPainterPath path;
            const Cliente& inicio = m_instancia.nodo(ruta[0]);
            path.moveTo(inicio.x, inicio.y);
            for (int k = 1; k < static_cast<int>(ruta.size()); ++k) {
                const Cliente& c = m_instancia.nodo(ruta[k]);
                path.lineTo(c.x, c.y);
            }
            QPen pluma(colorPorIndice(r));
            pluma.setWidth(2);
            m_escena->addPath(path, pluma);
        }
    }

    // 2) Dibujar los nodos encima de las líneas.
    if (!lod) {
        for (int i = 0; i < m_instancia.cantidadNodos(); ++i) {
            const Cliente& c = m_instancia.nodo(i);

            if (i == 0) {
                // Depósito: cuadrado grande negro.
                QPen   pluma(Qt::black);
                QBrush relleno(QColor(30, 30, 30));
                const double lado = 12.0;
                m_escena->addRect(c.x - lado/2, c.y - lado/2, lado, lado, pluma, relleno);

                auto* txt = m_escena->addSimpleText("DEPOSITO");
                txt->setPos(c.x + 10, c.y - 20);
            } else {
                // Cliente: círculo azul claro.
                QPen   pluma(QColor(60, 60, 60));
                QBrush relleno(QColor(120, 180, 240));
                const double r = 6.0;
                m_escena->addEllipse(c.x - r, c.y - r, 2*r, 2*r, pluma, relleno);

                auto* txt = m_escena->addSimpleText(QString::number(c.id));
                txt->setPos(c.x + 8, c.y - 8);
            }
        }
    } else {
        // Con miles de clientes las etiquetas de texto son ilegibles de
        // todas formas: se omiten (ni addSimpleText ni addEllipse por
        // nodo) y se agregan todos los círculos como UN solo QPainterPath.
        QPainterPath puntos;
        for (int i = 1; i < m_instancia.cantidadNodos(); ++i) {
            const Cliente& c = m_instancia.nodo(i);
            const double r = 6.0;
            puntos.addEllipse(c.x - r, c.y - r, 2*r, 2*r);
        }
        m_escena->addPath(puntos, QPen(QColor(60, 60, 60)), QBrush(QColor(120, 180, 240)));

        // El depósito sí se marca individualmente (un solo item extra).
        const Cliente& dep = m_instancia.nodo(0);
        const double lado = 12.0;
        m_escena->addRect(dep.x - lado/2, dep.y - lado/2, lado, lado,
                          QPen(Qt::black), QBrush(QColor(30, 30, 30)));
    }

    // 3) Ajustar la vista para que todo quepa en pantalla.
    fitInView(m_escena->sceneRect(), Qt::KeepAspectRatio);
}
