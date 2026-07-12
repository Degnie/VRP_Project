// ============================================================================
//  LectorInstancia.cpp
// ============================================================================
#include "LectorInstancia.h"

#include <exception>
#include <fstream>
#include <sstream>
#include <vector>

// Elimina espacios en blanco al inicio y al final de una cadena.
static std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

bool LectorInstancia::cargar(const std::string& rutaArchivo,
                             Instancia&         inst,
                             std::string&       error)
{
    std::ifstream f(rutaArchivo);
    if (!f.is_open()) {
        error = "No se pudo abrir el archivo: " + rutaArchivo;
        return false;
    }

    inst.limpiar();

    std::string nombre;
    int         dimension = 0;
    int         capacidad = 0;

    // Un solo vector<Cliente> (no 3 vectores paralelos xs/ys/demandas que
    // duplicarían la huella de memoria hasta el final): NODE_COORD_SECTION y
    // DEMAND_SECTION escriben directo sobre los mismos Cliente ya reservados.
    std::vector<Cliente> nodos;

    std::string linea;
    std::string seccion = "";   // qué sección estamos leyendo
    int         numLinea = 0;

    // Límite defensivo: un archivo corrupto no debería poder pedirnos que
    // reservemos una cantidad absurda de memoria.
    const int DIMENSION_MAXIMA = 1'000'000;

    try {
        while (std::getline(f, linea)) {
            ++numLinea;
            std::string t = trim(linea);
            if (t.empty()) continue;

            // Palabras clave: activan una sección o guardan un valor.
            if (t.rfind("NAME", 0) == 0) {
                size_t p = t.find(':');
                if (p != std::string::npos) nombre = trim(t.substr(p + 1));
                continue;
            }
            if (t.rfind("DIMENSION", 0) == 0) {
                size_t p = t.find(':');
                if (p == std::string::npos) {
                    error = "DIMENSION mal formada en la linea " + std::to_string(numLinea) + ".";
                    return false;
                }
                dimension = std::stoi(trim(t.substr(p + 1)));
                if (dimension <= 0 || dimension > DIMENSION_MAXIMA) {
                    error = "DIMENSION fuera de rango en la linea " + std::to_string(numLinea) + ".";
                    return false;
                }
                nodos.assign(dimension, Cliente());
                for (int k = 0; k < dimension; ++k) nodos[k].id = k;
                continue;
            }
            if (t.rfind("CAPACITY", 0) == 0) {
                size_t p = t.find(':');
                if (p == std::string::npos) {
                    error = "CAPACITY mal formada en la linea " + std::to_string(numLinea) + ".";
                    return false;
                }
                capacidad = std::stoi(trim(t.substr(p + 1)));
                continue;
            }
            if (t == "NODE_COORD_SECTION") { seccion = "COORD";  continue; }
            if (t == "DEMAND_SECTION")     { seccion = "DEMAND"; continue; }
            if (t == "EOF")                 break;

            // Datos dentro de una sección: se escriben directo sobre 'nodos',
            // sin arreglos intermedios.
            std::istringstream ss(t);
            if (seccion == "COORD") {
                int    id;
                double x, y;
                if (ss >> id >> x >> y) {
                    int idx = id - 1;    // los archivos usan 1..n; nosotros 0..n-1
                    if (idx >= 0 && idx < dimension) {
                        nodos[idx].x = x;
                        nodos[idx].y = y;
                    }
                }
            } else if (seccion == "DEMAND") {
                int id, d;
                if (ss >> id >> d) {
                    int idx = id - 1;
                    if (idx >= 0 && idx < dimension && idx != 0) nodos[idx].demanda = d;
                }
            }
        }
    } catch (const std::exception& e) {
        error = "Error al parsear la linea " + std::to_string(numLinea) + ": " + e.what();
        return false;
    }

    // Validaciones mínimas.
    if (dimension <= 0) {
        error = "DIMENSION invalida o no encontrada.";
        return false;
    }
    if (capacidad <= 0) {
        error = "CAPACITY invalida o no encontrada.";
        return false;
    }

    // Construcción final de la instancia. El nodo 0 (id=1 en el archivo) es
    // el depósito; ya quedó con demanda=0 (nunca se escribió arriba).
    inst.setNombre(nombre.empty() ? "sin_nombre" : nombre);
    inst.setCapacidad(capacidad);

    for (const Cliente& c : nodos) inst.agregarNodo(c);

    return true;
}
