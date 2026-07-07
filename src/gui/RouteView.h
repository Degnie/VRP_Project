// ============================================================================
//  RouteView.h
//  ----------------------------------------------------------------------------
//  Widget que muestra en pantalla los clientes y las rutas.
//  Está basado en QGraphicsView + QGraphicsScene (recomendado por Qt para
//  dibujos 2D con muchos elementos).
//
//  Uso:
//      RouteView view;
//      view.mostrar(instancia, solucion);
// ============================================================================
#ifndef ROUTEVIEW_H
#define ROUTEVIEW_H

#include <QGraphicsView>
#include <QGraphicsScene>
#include "../core/Instancia.h"
#include "../core/Solucion.h"

class RouteView : public QGraphicsView {
    Q_OBJECT

public:
    explicit RouteView(QWidget* parent = nullptr);

    // Dibuja los nodos y las rutas.
    // Si la solución está vacía se dibujan solo los nodos.
    void mostrar(const Instancia& inst, const Solucion& sol);

    // Borra el contenido de la escena.
    void limpiar();

private:
    QGraphicsScene* m_escena;

    // Devuelve un color distinto para cada índice de ruta (paleta cíclica).
    QColor colorPorIndice(int i) const;
};

#endif // ROUTEVIEW_H
