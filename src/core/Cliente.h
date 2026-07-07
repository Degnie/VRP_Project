// ============================================================================
//  Cliente.h
//  ----------------------------------------------------------------------------
//  Representa un nodo del problema (depósito o cliente).
//  El depósito siempre se guarda con id = 0 y demanda = 0.
// ============================================================================
#ifndef CLIENTE_H
#define CLIENTE_H

struct Cliente {
    int    id;        // Identificador único. El depósito tiene id = 0.
    double x;         // Coordenada X en el plano.
    double y;         // Coordenada Y en el plano.
    int    demanda;   // Unidades de producto que este cliente pide.

    Cliente(int id_ = 0, double x_ = 0.0, double y_ = 0.0, int demanda_ = 0)
        : id(id_), x(x_), y(y_), demanda(demanda_) {}
};

#endif // CLIENTE_H
