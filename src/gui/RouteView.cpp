// ============================================================================
//  RouteView.cpp
// ============================================================================
#include "RouteView.h"

#include <QPen>
#include <QBrush>
#include <QGraphicsEllipseItem>
#include <QGraphicsLineItem>
#include <QGraphicsSimpleTextItem>
#include <algorithm>
#include <limits>

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

void RouteView::mostrar(const Instancia& inst, const Solucion& sol) {
    m_escena->clear();

    if (inst.cantidadNodos() == 0) return;

    // 1) Buscar rango de coordenadas para escalar el dibujo.
    double xMin =  std::numeric_limits<double>::infinity();
    double xMax = -std::numeric_limits<double>::infinity();
    double yMin =  std::numeric_limits<double>::infinity();
    double yMax = -std::numeric_limits<double>::infinity();

    for (int i = 0; i < inst.cantidadNodos(); ++i) {
        const Cliente& c = inst.nodo(i);
        if (c.x < xMin) xMin = c.x;
        if (c.x > xMax) xMax = c.x;
        if (c.y < yMin) yMin = c.y;
        if (c.y > yMax) yMax = c.y;
    }
    // Margen para que los puntos no se peguen al borde.
    double margen = 40.0;
    m_escena->setSceneRect(xMin - margen, yMin - margen,
                           (xMax - xMin) + 2 * margen,
                           (yMax - yMin) + 2 * margen);

    // 2) Dibujar las rutas (líneas).
    for (int r = 0; r < sol.cantidadRutas(); ++r) {
        const Ruta& ruta = sol.ruta(r);
        QPen pluma(colorPorIndice(r));
        pluma.setWidth(2);

        for (int k = 0; k + 1 < static_cast<int>(ruta.size()); ++k) {
            const Cliente& a = inst.nodo(ruta[k]);
            const Cliente& b = inst.nodo(ruta[k + 1]);
            m_escena->addLine(a.x, a.y, b.x, b.y, pluma);
        }
    }

    // 3) Dibujar los nodos encima de las líneas.
    for (int i = 0; i < inst.cantidadNodos(); ++i) {
        const Cliente& c = inst.nodo(i);

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

    // 4) Ajustar la vista para que todo quepa en pantalla.
    fitInView(m_escena->sceneRect(), Qt::KeepAspectRatio);
}
