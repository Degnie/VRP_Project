# Guía de uso del sistema de prompts

Cómo se instala, cómo se invoca cada prompt y qué decir exactamente en cada paso.

---

## 1 · Dónde viven los prompts

**Fuente canónica.** Un repositorio propio, aparte de los proyectos. Es el único lugar donde se edita un prompt.

```
/agent-workflow                    ← repositorio canónico, se edita solo aquí
├── VERSION                        ← una línea: 1.0
├── GUIA_DE_USO.md
├── INDICE_DEL_SISTEMA.md
├── plantillas/
│   └── SPEC.md
└── prompts/
    ├── 00-bloque-claude.md
    ├── 00-bloque-gemini.md
    ├── 01-descubrimiento-gemini.md
    ├── 01M-migracion-gemini.md
    ├── 01A-adopcion-gemini.md
    ├── 01B-adopcion-claude.md
    ├── 02-arquitectura-gemini.md
    ├── 03-implementacion-claude.md
    ├── 04-revision-gemini.md
    ├── 05-visual-borrador-claude.md
    ├── 06-visual-auditoria-gemini.md
    ├── 07-infra-gemini.md
    ├── 08-empaquetado-gemini.md
    ├── 09-entrega-cliente-gemini.md
    ├── 10-cambio-analisis-gemini.md
    ├── 11-cambio-implementacion-claude.md
    └── 12-auditoria-roles-claude.md
```

**Copia por proyecto.** Al iniciar cualquier proyecto, copias `prompts/` y `VERSION` a su raíz:

```
/mi-proyecto
├── prompts/          ← copia, NO se edita aquí
│   └── VERSION       ← 1.0
├── SPEC.md
├── README.md
├── CHANGELOG.md
├── TESTING_STRATEGY.md
├── verify
├── docs/adr/
├── src/
└── tests/
```

**El nombre del agente va en el archivo a propósito.** Es lo que evita pegarle a Gemini un prompt de Claude, que es el error más fácil de cometer y el más difícil de notar.

**Regla de una sola fuente.** Si un prompt necesita cambiar, se cambia en el repositorio canónico, se sube `VERSION`, y los proyectos activos se actualizan copiando de nuevo. **Nunca edites un prompt dentro de un proyecto.** Un arreglo hecho ahí no llega a ningún otro proyecto y, seis meses después, tienes cinco versiones distintas del mismo prompt sin saber cuál es la buena.

**Detección de divergencia.** Compara `VERSION` del proyecto contra la canónica. Si no coinciden, el proyecto corre con prompts viejos.

---

## 2 · Cómo se invoca

Ambos agentes leen la carpeta, así que no se pega nada: se les indica el archivo.

**Estructura de toda invocación:**

```
Lee prompts/[archivo].md y adopta esas instrucciones como tu rol para
esta sesión. Confirma con la frase de arranque que indica el prompt y
espera mis datos.
```

**Al inicio de cada sesión nueva sobre un proyecto en curso**, antes de cualquier otra cosa:

```
Antes de empezar: lee SPEC.md, CHANGELOG.md —incluida la sección
### Rechazado / Descartado— y los ADRs. Resume en tres líneas dónde
está el proyecto y qué quedó pendiente.
```

Esto no es opcional. Ninguno de los dos agentes recuerda la sesión anterior; el repositorio es la memoria, y esa frase la carga.

---

## 3 · Caso A · Proyecto libre nuevo

**Paso 1 · Descubrimiento** → Gemini

```
Lee prompts/01-descubrimiento-gemini.md y adopta esas instrucciones
como tu rol. Este es un [PROYECTO LIBRE]. Confirma y espera mi lluvia
de ideas.
```

Termina cuando `SPEC.md` está escrito y commiteado.

**Paso 2 · Arquitectura** → Gemini

```
Lee prompts/02-arquitectura-gemini.md y adopta esas instrucciones como
tu rol. SPEC.md ya está en la raíz. Inicia la FASE 1.
```

Termina con ADR-001, ADR-002 y `TESTING_STRATEGY.md` escritos.

**Paso 3 · Implementación** → Claude

```
Lee prompts/03-implementacion-claude.md y adopta esas instrucciones
como tu rol. SPEC.md, los ADRs y TESTING_STRATEGY.md ya están en el
proyecto. Inicia la ETAPA 0.
```

La etapa 2 es tu punto de revisión principal: apruebas la tabla de trazabilidad antes de que exista una línea de implementación.

**Paso 4 · Revisión** → Gemini

```
Lee prompts/04-revision-gemini.md y adopta esas instrucciones como tu
rol. Ejecuta verify por tu cuenta y revisa git log antes de opinar.
Inicia la Etapa 1.
```

**Cierre** → Gemini, uno de los dos:

```
Lee prompts/08-empaquetado-gemini.md y adopta esas instrucciones como
tu rol. Inicia.
```

```
Lee prompts/09-entrega-cliente-gemini.md y adopta esas instrucciones
como tu rol. Inicia la Etapa 1.
```

---

## 4 · Caso B · Migración de universitario a libre

**Paso 1 · Extracción y benchmarking** → Gemini

```
Lee prompts/01M-migracion-gemini.md y adopta esas instrucciones como
tu rol. El repositorio heredado está en [ruta]. El proyecto nuevo va
en [ruta]. Inicia la FASE 1.
```

Sustituye al paso 1 del Caso A. Produce `SPEC.md` y `docs/BENCHMARKING.md`.

**A partir de ahí, el flujo es idéntico al Caso A** desde el paso 2. El prompt de arquitectura detecta `docs/BENCHMARKING.md` y lo incorpora solo.

**Si el proyecto académico ya tenía `SPEC.md`**, la migración es mucho más corta:

```
Lee prompts/01M-migracion-gemini.md y adopta esas instrucciones como
tu rol. Ya existe SPEC.md del proyecto original: salta las FASES 1 a 3
y empieza en la FASE 4, frontera de la migración.
```

---

## 5 · Caso C · Proyecto libre existente que se adopta al sistema

Para un proyecto que ya funciona, construido con el sistema anterior. **No se cambia el stack, ni la arquitectura, ni el comportamiento.**

**Paso 1 · Reconstrucción** → Gemini

```
Lee prompts/01A-adopcion-gemini.md y adopta esas instrucciones como tu
rol. Este proyecto se construyó con un sistema anterior y quiero
adoptarlo al nuevo. Inicia la ETAPA 0.
```

Su Etapa 0 te va a recomendar **adoptar o regenerar**. Hazle caso: en un proyecto pequeño, correr el flujo normal desde cero suele salir más barato y deja una historia coherente.

**Paso 2 · Aplicación** → Claude

```
Lee prompts/01B-adopcion-claude.md y adopta esas instrucciones como tu
rol. El plan está en docs/plan-adopcion.md. Inicia la ETAPA 0.
```

**Paso 3** → la primera auditoría bajo el sistema nuevo, con `prompts/04-revision-gemini.md`. De ahí en adelante, el flujo normal.

**Qué esperar.** La etapa de mapeo es la que hace el trabajo: cada test se contrasta contra una regla, y **los que no mapean contra ninguna son los rebuscados**. Es la primera vez que ese problema se vuelve visible en lugar de acumularse.

**Dos cosas que no se pueden retrofitear**, y por eso el sistema las declara en vez de fingirlas:

- El historial anterior no tiene evidencia de tests-antes-que-código y no puede tenerla. Por eso se marca una línea de corte en el `README`: sin ella, cada auditoría futura reportaría hallazgos falsos sobre todo el pasado del proyecto.
- El umbral de mutación se **mide primero** y se fija por debajo de lo medido. Un umbral aspiracional que falla desde el primer día termina desactivado, y entonces no protege nada.

**Las mejoras detectadas durante la adopción no se implementan durante la adopción.** Ambos prompts las reportan aparte. Se tratan después, con el bucle de cambios normal — mezclarlas contamina el punto de comparación que garantiza que el comportamiento no cambió.

---

## 6 · Bucle de cambios

Se usa cada vez que aparece un requerimiento nuevo, en cualquier momento después del paso 3.

**Análisis** → Gemini

```
Lee prompts/10-cambio-analisis-gemini.md y adopta esas instrucciones
como tu rol. Inicia la FASE 1 con esta solicitud:

[la conversación con el cliente, o tu propia solicitud]
```

**Implementación** → Claude

```
Lee prompts/11-cambio-implementacion-claude.md y adopta esas
instrucciones como tu rol. El delta está en docs/delta-actual.md y
SPEC.md ya está actualizado. Inicia la ETAPA 0.
```

Después vuelve al paso 4, revisión.

---

## 7 · Ramas condicionales

Ninguna es obligatoria. Cada una tiene su condición.

**Visual** — solo si el producto tiene interfaz.

```
Lee prompts/05-visual-borrador-claude.md y adopta esas instrucciones
como tu rol. Inicia el PASO 0.
```

```
Lee prompts/06-visual-auditoria-gemini.md y adopta esas instrucciones
como tu rol. Inicia la Etapa 1.
```

**Infraestructura** — solo si hay despliegue.

```
Lee prompts/07-infra-gemini.md y adopta esas instrucciones como tu
rol. Inicia la Etapa 1.
```

**Auditoría por roles** — solo si el producto tiene roles de usuario distinguibles. Su propio Paso 0 decide si aplica; si dice que no, hazle caso.

```
Lee prompts/12-auditoria-roles-claude.md y adopta esas instrucciones
como tu rol. Los roles del producto son: [lista]. Inicia el PASO 0.
```

---

## 8 · Prompts antiguos que se conservan

Cinco de tus prompts originales siguen en uso. Hay que pasarlos a `.md`, ponerles el bloque común de Gemini y aplicarles las ediciones ya definidas.

| Archivo nuevo | Origen | Ediciones a aplicar |
| --- | --- | --- |
| `04-revision-gemini.md` | `4. Revisa GEMINI` | Bloque común · desambiguar el ciclo · cortar la solicitud directa de tests en Etapa 2 · añadir `SPEC.md` a la lectura · quitar `agent_bridge.md` · quitar Graphify |
| `06-visual-auditoria-gemini.md` | `5. Pinta GEMINI` | Bloque común · desambiguar el ciclo · ampliar lectura a `CHANGELOG` y ADRs · quitar `agent_bridge.md` · quitar Graphify |
| `07-infra-gemini.md` | `6. Sube GEMINI` | Bloque común · desambiguar el ciclo · ampliar lectura a `CHANGELOG`, ADRs y `RNF` · quitar `agent_bridge.md` · quitar Graphify |
| `08-empaquetado-gemini.md` | `7. Empaqueta GEMINI` | Bloque común · quitar `agent_bridge.md` · quitar Graphify |
| `09-entrega-cliente-gemini.md` | `8. Envio Cliente` | Bloque común solamente. Su ciclo ya está bien redactado |

El detalle exacto de cada edición está en la sección "Ediciones exactas" del bloque común de Gemini.

**Los ocho restantes se eliminan.** Están listados en la sección 8 del índice del sistema.

---

## 9 · Cuando el agente se desvía

Frases de corrección, para usar en el momento y no al final:

**Si empieza a producir de más:**

```
Detente. Estás fuera del alcance declarado en la etapa 0. Vuelve a la
lista de archivos que aprobamos y dime qué te empujó a salir de ella.
```

**Si escribe un test que no reconoces:**

```
Ese test no cita ningún ID de SPEC.md. Según la regla 3, un test nuevo
exige una regla nueva. Propónmela como RN o EC y espera, o elimínalo.
```

**Si modifica un test para hacer pasar algo:**

```
Los tests aprobados no se modifican. Revierte ese cambio y explícame
por qué el test te parecía equivocado.
```

**Si encadena etapas sin esperar:**

```
Una etapa a la vez. Vuelve al final de la etapa [n] y espera mi
confirmación.
```

**Si Gemini toca código:**

```
Escribes solo documentación. Revierte ese cambio y repórtalo como
hallazgo para que lo implemente Claude.
```

---

## 10 · Orden de instalación en un proyecto nuevo

1. Crea el repositorio vacío e inicializa git.
2. Copia `prompts/` y `VERSION` desde el repositorio canónico.
3. Primer commit: `chore: instalación del sistema de prompts v[versión]`.
4. Invoca el paso 1.

A partir de ahí, el propio flujo crea todo lo demás.
