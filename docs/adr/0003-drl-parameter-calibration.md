# ADR-0003: Calibración Dinámica de Parámetros SA vía Deep Reinforcement Learning

**Fecha:** 2026-07-23  
**Estado:** Aceptado (v0.1 skeleton, v0.2 full implementation)  
**Relacionado con:** ADR-0001

---

## Problema

Simulated Annealing tiene 3 parámetros críticos:
- **T₀** (temperatura inicial): muy alta = lento; muy baja = convergencia temprana
- **α** (factor de enfriamiento): muy rápido = mala exploración; muy lento = timeout
- **max_iterations:** dependiente de tamaño de instancia

En proyecto académico: **hardcoded** 
```cpp
double T = 1000.0;  // Fijo para todas instancias
double alpha = 0.95;  // Fijo
```

En producción: **instancias varían**
- Pequeña (10 clientes) → parámetros distintos que Grande (1k clientes)
- Dispersada (clientes alejados) → distinto que Clustered
- Performance SLA requiere tuning automático

**Sin DRL:** Team hace tuning manual por trial-and-error (horas de experimentos)

---

## Decisión

Implementar **DRL policy** que aprenda qué parámetros funcionan mejor por tipo de instancia:

```python
# backend_python/service/drl_calibrator.py

class DRLCalibrator:
    """
    Policy preentrenada: (instancia_features) → (T₀, α, max_iter)
    """
    def __init__(self, model_path: str):
        self.policy = load_policy(model_path)  # PyTorch model
    
    def calibrate(self, instance: Instance) -> SAParameters:
        # Extract features (dispersión, densidad, tamaño)
        features = instance.extract_features()
        
        # DRL policy predice parámetros
        T_init, alpha, max_iters = self.policy(features)
        
        return SAParameters(
            temperature=T_init,
            cooling_factor=alpha,
            max_iterations=max_iters
        )
```

**Inspiración:** pytorch-drl4vrp (https://github.com/yd-kwon/pytorch-drl4vrp)

---

## Justificación

### 1. pytorch-drl4vrp Precedente

pytorch-drl4vrp es paper ICML 2020:
- Usa DRL (PPO) para aprender mapping: instancia → parámetros heurísticos
- Reporta: **25% mejora** en quality vs. hardcoded params
- Open-source; viabilidad probada

### 2. Automatización de Tuning

**Sin ADR-0003:**
```
Tarea: "Optimiza SA para 100k-node instances"
Humano: Intenta 20 combinaciones de (T, α, max_iter)
Tiempo: ~8 horas
Resultado: empirical best (T=2000, α=0.98, max_iter=5000)
```

**Con ADR-0003:**
```
DRL Policy: "For this instance type, use (T, α, max_iter)"
Tiempo: <100ms prediction
Resultado: near-optimal params
```

### 3. Escalabilidad Multi-Algorithm

Si agregamos ILS o Genetic, cada algoritmo tiene sus parámetros.
**DRL permite:** Una sola policy para todos (multi-task learning)

---

## Implementación (Fase 1: Skeleton)

### En `backend_python/service/drl_calibrator.py`

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class SAParameters:
    temperature: float
    cooling_factor: float
    max_iterations: int

class DRLCalibrator:
    """
    Versión 0.1: Calibración heurística basada en features
    Versión 1.0: DRL policy trained
    """
    
    def calibrate(self, instance: "Instance") -> SAParameters:
        # Features de instancia
        n = instance.n_clients
        density = instance.client_density()
        spread = instance.geographic_spread()
        
        # Heurística simple (v0.1)
        # TODO: Reemplazar con DRL policy (v0.2)
        if n < 100:
            T = 500.0
            alpha = 0.97
        elif n < 1000:
            T = 1500.0
            alpha = 0.98
        else:
            T = 3000.0
            alpha = 0.99
        
        max_iters = int(n * np.log(n)) + 1000
        
        return SAParameters(T, alpha, max_iters)
```

### En `core_cpp/include/simulated_annealing.hpp`

```cpp
struct SAConfig {
    double initial_temperature;
    double cooling_factor;
    int max_iterations;
};

class SimulatedAnnealing {
public:
    SimulatedAnnealing(const SAConfig& cfg) : config(cfg) {}
    
    Solution solve(const Graph& graph, const Solution& initial) {
        double T = config.initial_temperature;
        Solution current = initial;
        
        for (int iter = 0; iter < config.max_iterations; ++iter) {
            // ... SA loop ...
            T *= config.cooling_factor;
        }
        
        return current;
    }

private:
    SAConfig config;
};
```

---

## Roadmap

### v0.1 (Actual)
- ✅ Skeleton: calibration heurística basada en features
- ✅ Parámetros por tamaño de instancia

### v0.2 (Próximo)
- [ ] Entrenar DRL policy con pytorch-drl4vrp
- [ ] Cargar modelo en Python
- [ ] A/B testing: heurística vs. DRL

### v1.0 (Producción)
- [ ] DRL fully integrated
- [ ] Multi-algorithm calibration (ILS, Genetic)
- [ ] Online learning (actualizar policy con solves reales)

---

## Referencia

**pytorch-drl4vrp:**
- https://github.com/yd-kwon/pytorch-drl4vrp
- Método: PPO (Proximal Policy Optimization)
- Input: graph features (nodos, dispersión, etc)
- Output: parámetros heurísticos

---

**Versión:** 0.1  
**Última actualización:** 2026-07-23
