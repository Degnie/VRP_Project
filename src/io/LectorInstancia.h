// ============================================================================
//  LectorInstancia.h
//  ----------------------------------------------------------------------------
//  Lee una instancia del VRP desde un archivo de texto con formato tipo CVRPLIB
//  simplificado:
//
//      NAME : ejemplo_10
//      DIMENSION : 10
//      CAPACITY : 40
//      NODE_COORD_SECTION
//      1  50.0  50.0
//      2  17.3  92.4
//      ...
//      DEMAND_SECTION
//      1  0
//      2  5
//      ...
//      EOF
//
//  El primer nodo (id=1) se toma como depósito y se guarda internamente con
//  índice 0. Los demás pasan a ser los clientes 1..n-1.
// ============================================================================
#ifndef LECTORINSTANCIA_H
#define LECTORINSTANCIA_H

#include "../core/Instancia.h"
#include <string>

class LectorInstancia {
public:
    // Devuelve true si pudo leer y llenar 'inst' correctamente.
    // Si algo falla, deja un mensaje en 'error'.
    static bool cargar(const std::string& rutaArchivo,
                       Instancia&         inst,
                       std::string&       error);
};

#endif // LECTORINSTANCIA_H
