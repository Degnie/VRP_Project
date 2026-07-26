import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  // Nombre corto del área que protege, para el mensaje visible (ej. "el mapa").
  label: string;
}

interface State {
  error: Error | null;
}

// Sin esto, cualquier excepción no capturada durante el render (ej. MapLibre
// rechazando una coordenada fuera de rango) tumbaba el árbol de React
// completo — pantalla en blanco, sin ningún mensaje, reproducido en vivo
// durante la auditoría. React no tiene una forma funcional/hook de esto
// todavía — un class component con getDerivedStateFromError es la única API.
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Error en ${this.props.label}:`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="error-message" role="alert">
          Ocurrió un problema mostrando {this.props.label}. Revisá los datos cargados
          (coordenadas, etc.) — si el problema sigue, recargá la página.
        </div>
      );
    }
    return this.props.children;
  }
}
