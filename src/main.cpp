// ============================================================================
//  main.cpp
//  ----------------------------------------------------------------------------
//  Punto de entrada. Solo crea la aplicación Qt y la ventana principal.
// ============================================================================
#include <QApplication>
#include "gui/MainWindow.h"

int main(int argc, char* argv[]) {
    QApplication app(argc, argv);

    MainWindow ventana;
    ventana.show();

    return app.exec();
}
