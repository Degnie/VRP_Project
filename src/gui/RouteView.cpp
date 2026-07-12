// ============================================================================
//  RouteView.cpp
// ============================================================================
#include "RouteView.h"

#include <QPen>
#include <QBrush>
#include <QGraphicsEllipseItem>
#include <QGraphicsLineItem>
#include <QGraphicsPathItem>
#include <QGraphicsPixmapItem>
#include <QGraphicsSimpleTextItem>
#include <QImage>
#include <QPainter>
#include <QPainterPath>
#include <QPixmap>
#include <QPointF>
#include <QPolygonF>
#include <QTimer>
#include <QWheelEvent>
#include <algorithm>
#include <limits>
#include <vector>

// Por encima de este tamaño, dejamos de crear un QGraphicsItem por nodo/
// segmento (miles de items individuales hacen que Qt se arrastre al
// repintar/hacer zoom) y pasamos a dibujar en lote.
static const int LOD_UMBRAL_NODOS = 500;

// Lado máximo (px) del raster donde se precalculan los puntos de cliente en
// modo LOD. Capado para no pedir, por ejemplo, un QImage de 10000x10000
// (400 MB a 32bpp) cuando la instancia cubre un área grande: el raster se
// escala de vuelta al tamaño real de la escena vía QGraphicsItem::setScale.
static const int LOD_RASTER_MAX = 2000;

RouteView::RouteView(QWidget* parent)
    : QGraphicsView(parent)
{
    m_escena = new QGraphicsScene(this);
    setScene(m_escena);
    setRenderHint(QPainter::Antialiasing, true);
    setBackgroundBrush(QBrush(QColor(250, 250, 250)));

    // Reactiva el antialiasing ~100ms después del último evento de rueda
    // (ver wheelEvent). Single-shot: cada nuevo scroll lo reinicia.
    m_timerAntialiasing = new QTimer(this);
    m_timerAntialiasing->setSingleShot(true);
    connect(m_timerAntialiasing, &QTimer::timeout, this, [this]() {
        setRenderHint(QPainter::Antialiasing, true);
        viewport()->update();
    });
}

void RouteView::limpiar() {
    m_escena->clear();
    m_bboxValido = false;
}

QColor RouteView::colorPorIndice(int i) const {
    // Paleta Okabe-Ito: distinguible para las formas más comunes de
    // daltonismo (protanopia/deuteranopia/tritanopia). Se cicla si hay más
    // rutas que colores; el estilo de línea (ver estiloPorIndice) evita que
    // dos rutas consecutivas dependan solo del color para diferenciarse.
    static const QColor paleta[] = {
        QColor(0x00, 0x72, 0xB2),   // azul
        QColor(0xE6, 0x9F, 0x00),   // naranja
        QColor(0x00, 0x9E, 0x73),   // verde azulado
        QColor(0xCC, 0x79, 0xA7),   // púrpura rojizo
        QColor(0xD5, 0x5E, 0x00),   // bermellón
        QColor(0x56, 0xB4, 0xE9),   // azul cielo
        QColor(0xF0, 0xE4, 0x42),   // amarillo
    };
    const int total = sizeof(paleta) / sizeof(paleta[0]);
    return paleta[i % total];
}

Qt::PenStyle RouteView::estiloPorIndice(int i) const {
    // Ciclo de 4 (coprimo con los 7 colores de arriba): la combinación
    // color+estilo tarda 28 rutas en repetirse, no 7.
    static const Qt::PenStyle estilos[] = {
        Qt::SolidLine, Qt::DashLine, Qt::DotLine, Qt::DashDotLine,
    };
    const int total = sizeof(estilos) / sizeof(estilos[0]);
    return estilos[i % total];
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
            pluma.setStyle(estiloPorIndice(r));

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
            pluma.setStyle(estiloPorIndice(r));
            m_escena->addPath(path, pluma);
        }
    }

    // 2) Dibujar los nodos encima de las líneas.
    if (!lod) {
        for (int i = 0; i < m_instancia.cantidadNodos(); ++i) {
            const Cliente& c = m_instancia.nodo(i);

            if (i == 0) {
                dibujarDeposito(c.x, c.y);
                auto* txt = m_escena->addSimpleText("DEPÓSITO");
                txt->setPos(c.x + 12, c.y - 8);
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
        // Con miles/millones de clientes, un QPainterPath con una elipse
        // vectorial por nodo satura el teselador de Qt (cada elipse es una
        // curva Bézier que hay que rasterizar en cada repintado/zoom).
        // En su lugar: rasterizamos los puntos UNA sola vez con
        // QPainter::drawPoints sobre un QImage cacheado (mucho más barato:
        // un simple lote de píxeles) y lo insertamos como un único
        // QGraphicsPixmapItem — de O(n) curvas vectoriales a 1 solo bitmap.
        QRectF area = m_escena->sceneRect();
        double ladoMayor = std::max(area.width(), area.height());
        double escala = (ladoMayor > LOD_RASTER_MAX) ? LOD_RASTER_MAX / ladoMayor : 1.0;

        int anchoRaster = std::max(1, static_cast<int>(area.width()  * escala));
        int altoRaster   = std::max(1, static_cast<int>(area.height() * escala));

        QImage raster(anchoRaster, altoRaster, QImage::Format_ARGB32_Premultiplied);
        raster.fill(Qt::transparent);

        std::vector<QPointF> puntos;
        puntos.reserve(static_cast<size_t>(std::max(0, m_instancia.cantidadNodos() - 1)));
        for (int i = 1; i < m_instancia.cantidadNodos(); ++i) {
            const Cliente& c = m_instancia.nodo(i);
            puntos.emplace_back((c.x - area.left()) * escala, (c.y - area.top()) * escala);
        }

        {
            QPainter pintor(&raster);
            pintor.setRenderHint(QPainter::Antialiasing, false);
            pintor.setPen(QPen(QColor(60, 60, 60), 2));
            pintor.drawPoints(puntos.data(), static_cast<int>(puntos.size()));
        }

        auto* item = m_escena->addPixmap(QPixmap::fromImage(raster));
        item->setPos(area.left(), area.top());
        item->setScale(1.0 / escala);

        // El depósito sí se marca individualmente (un solo item extra).
        const Cliente& dep = m_instancia.nodo(0);
        dibujarDeposito(dep.x, dep.y);
    }

    // 3) Ajustar la vista para que todo quepa en pantalla.
    fitInView(m_escena->sceneRect(), Qt::KeepAspectRatio);
}

void RouteView::dibujarDeposito(double x, double y) {
    const double r = 9.0;
    QPolygonF rombo;
    rombo << QPointF(x, y - r) << QPointF(x + r, y) << QPointF(x, y + r) << QPointF(x - r, y);

    QPen   pluma(QColor(0xFF, 0xFF, 0xFF));
    pluma.setWidth(2);
    QBrush relleno(QColor(0x07, 0x3B, 0x4C));   // navy oscuro, no compite con la paleta de rutas
    m_escena->addPolygon(rombo, pluma, relleno);
}

void RouteView::wheelEvent(QWheelEvent* event) {
    // LOD adaptativo: sacrificamos antialiasing durante la interacción para
    // no perder FPS con miles de nodos en pantalla; se reactiva solo (ver
    // ctor) cuando el usuario deja de mover la rueda por ~100ms.
    setRenderHint(QPainter::Antialiasing, false);
    m_timerAntialiasing->start(100);

    const double factor = (event->angleDelta().y() > 0) ? 1.15 : 1.0 / 1.15;
    scale(factor, factor);
    event->accept();
}
