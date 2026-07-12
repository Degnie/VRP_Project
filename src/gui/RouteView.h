// ============================================================================
//  RouteView.h
//  ----------------------------------------------------------------------------
//  Widget que muestra en pantalla los clientes y las rutas.
//  Está basado en QGraphicsView + QGraphicsScene (recomendado por Qt para
//  dibujos 2D con muchos elementos).
//
//  Uso:
//      RouteView view;
//      view.mostrar(instancia, solucion);       // instancia nueva o editada
//      view.mostrarSolucion(otraSolucion);       // misma instancia, nueva solución
// ============================================================================
#ifndef ROUTEVIEW_H
#define ROUTEVIEW_H

#include <QGraphicsView>
#include <QGraphicsScene>
#include "../core/Instancia.h"
#include "../core/Solucion.h"

class QTimer;
class QWheelEvent;

class RouteView : public QGraphicsView {
    Q_OBJECT

public:
    explicit RouteView(QWidget* parent = nullptr);

    // Recalcula el bounding box para 'inst' y dibuja nodos + rutas de 'sol'.
    // Llamar cuando la instancia es nueva o cambió (carga, agregar cliente).
    void mostrar(const Instancia& inst, const Solucion& sol);

    // Redibuja usando la última instancia y bounding box ya calculados
    // (no vuelve a recorrer las coordenadas). Llamar cuando solo cambió la
    // solución (p.ej. tras correr Greedy/SA sobre la misma instancia).
    void mostrarSolucion(const Solucion& sol);

    // Borra el contenido de la escena.
    void limpiar();

protected:
    // LOD adaptativo: durante el zoom con la rueda, se desactiva el
    // antialiasing (más FPS con miles de nodos en pantalla) y se reactiva
    // solo cuando el usuario deja de interactuar (~100ms sin más eventos).
    void wheelEvent(QWheelEvent* event) override;

private:
    QGraphicsScene* m_escena;
    QTimer*         m_timerAntialiasing;

    Instancia m_instancia;      // última instancia dibujada (para mostrarSolucion)
    bool      m_bboxValido = false;
    double    m_xMin = 0.0, m_xMax = 0.0, m_yMin = 0.0, m_yMax = 0.0;

    void calcularBoundingBox();
    void dibujar(const Solucion& sol);
    // Marcador del depósito: un rombo (más distinguible que un cuadrado
    // liso) en un tono navy oscuro, con un anillo claro para que resalte
    // incluso sobre rutas de colores oscuros.
    void dibujarDeposito(double x, double y);

    // Color de la paleta Okabe-Ito (colorblind-safe) para el índice de ruta.
    QColor colorPorIndice(int i) const;
    // Estilo de línea (sólida/punteada/rayada/...) para el índice de ruta:
    // las rutas no dependen solo del color para distinguirse.
    Qt::PenStyle estiloPorIndice(int i) const;
};

#endif // ROUTEVIEW_H
