# Índice del sistema de prompts

Referencia operativa: qué prompt usar en cada momento, qué lee y qué produce.

---

## 0 · Supuesto de entorno

Ambos agentes corren en el mismo IDE con acceso directo a la carpeta del proyecto. Consecuencias:

- **Nada se pega.** Los prompts referencian rutas; los agentes leen los archivos.
- **Gemini escribe sus propios artefactos:** `SPEC.md`, ADRs y `TESTING_STRATEGY.md`. Nunca código ni tests.
- **Claude escribe código y tests.** Nunca documentación de especificación ni ADRs.
- **El auditor verifica por sí mismo:** ejecuta `verify` y lee `git log` en vez de confiar en lo que el implementador reporta.

Esa última línea es la que sostiene la separación de poderes. Un auditor que solo lee lo que el implementador le muestra no es un auditor.

---

## 1 · Estructura canónica

```
/proyecto
├── README.md              # etiqueta en línea 1 + arquitectura en dos niveles
├── SPEC.md                # la especificación con IDs
├── CHANGELOG.md           # incluye ### Rechazado / Descartado
├── TESTING_STRATEGY.md
├── verify                 # script o Makefile
├── docs/adr/
│   ├── ADR-001-stack-y-arquitectura.md
│   └── ADR-002-estrategia-verificacion.md
├── src/
└── tests/
```

Los cinco archivos de raíz son deliberados: son lo que un evaluador humano debe ver en diez segundos. Si cambias las rutas, el `grep` de trazabilidad de `verify` cambia con ellas.

---

## 2 · Caso A · Proyecto libre nuevo

| # | Prompt | Agente | Lee | Escribe |
|---|---|---|---|---|
| 1 | Descubrimiento | Gemini | tu lluvia de ideas | `SPEC.md` |
| 2 | Arquitectura | Gemini | `SPEC.md` | ADR-001, ADR-002, `TESTING_STRATEGY.md`, sección del README |
| 3 | Implementación | Claude | `SPEC.md`, ADRs, `TESTING_STRATEGY.md` | repo completo, tests, `verify`, `CHANGELOG.md` |
| 4 | Revisa | Gemini | todo + `verify` + `git log` | hallazgos; propone reglas nuevas |
| 5.x | Repinta | Claude | `SPEC.md` (glosario y `CU`) | vistas y estilos |
| 5 | Pinta | Gemini | vistas + `CHANGELOG.md` | hallazgos visuales |
| 6 | Sube | Gemini | config + `RNF` del `SPEC` | hallazgos de infraestructura |
| 7 u 8 | Empaqueta / Envío | Gemini | todo | README de portafolio o manual de instalación |

**Puertas de control.** Tres momentos donde apruebas y sin los cuales el flujo no avanza: el `SPEC` completo al cerrar el prompt 1, el manifiesto de archivos en la etapa 0 del prompt 3, y **la tabla de trazabilidad en la etapa 2 del prompt 3** — esta última es la más importante del sistema, porque es donde revisas los tests cuando son lo único escrito.

**Bucle de cambios**, en cualquier momento después del 3: `Ideas_Nuevas` Gemini → apruebas el delta → Gemini actualiza `SPEC.md` → `Ideas_Nuevas` Claude → `verify` → vuelve al 4.

**Ramas condicionales.** 5.x y 5 solo si hay interfaz. 6 solo si hay despliegue. Auditoría por roles solo si su Paso 0 confirma que los roles son distinguibles. 7 y 8 son excluyentes: portafolio o cliente.

---

## 3 · Caso B · Proyecto universitario nuevo

Mismo tronco, perfil reducido. No es un sistema distinto.

| Prompt | Cómo cambia |
|---|---|
| 1 Descubrimiento | Igual. El `SPEC` vale lo mismo con nota que sin ella |
| 2 Arquitectura | **La Fase 2 no compara stacks.** El profesor lo impone: se registra en ADR-001 como restricción externa, declarando que no se evaluaron alternativas y por qué |
| 3 Implementación | Igual, con `verify` reducido |
| 4 Revisa | Solo Etapas 1 y 2 |
| 5.x / 5 | Solo si el curso exige interfaz |
| 6, 7, 8 | No aplican |

**`verify` reducido:** compilación, suite en verde y trazabilidad. Sin umbral de mutación, sin regla de frontera.

Registrar el stack impuesto no es burocracia. En la defensa, poder explicar **por qué no elegiste** —y qué habrías elegido sin la restricción— es lo que distingue a alguien que entendió el problema de alguien que siguió instrucciones.

**Hueco conocido:** no existe prompt de entrega académica. La etapa de rúbrica, artefactos del curso (UML, informes) y preparación de defensa queda fuera del sistema y hoy la trabajas a mano.

---

## 4 · Caso C · Universitario que se vuelve libre

Dos variantes, con costos muy distintos.

**C1 · Planificado.** Sabes desde el inicio que va a graduarse. Corres el Caso B **manteniendo `SPEC.md` desde el día uno**, y al terminar el curso la compuerta G1 casi no cuesta: el dominio ya está especificado con IDs, así que la parte cara de la migración —reconstruir las reglas leyendo código— ya está hecha. Solo corres las fases 4 a 6 del prompt 1-M: frontera de la migración, benchmarking y consolidación.

**C2 · Rescate.** El proyecto ya existe y no tiene `SPEC`. Corres el prompt 1-M completo: extracción del núcleo por ingeniería inversa, eventos y glosario, casos límite y vacíos, frontera, benchmarking, consolidación.

En ambos casos, después: prompt 2 con etiqueta `[PROYECTO LIBRE]` y `verify` en perfil completo → prompt 3 → tronco normal.

**Reglas de la compuerta.** El curso debe estar cerrado y calificado. Si fue en equipo, resuelve la autoría antes de publicar. El `CHANGELOG` **se conserva** con un encabezado de etapa nueva: la continuidad del historial es lo que hace que se lea como evolución y no como un proyecto que empezó dos veces. La etiqueta del README pasa a `[PROYECTO LIBRE]`.

La diferencia de costo entre C1 y C2 es el argumento más fuerte para escribir `SPEC.md` también en los proyectos académicos, aunque el curso no lo pida.

---

## 4bis · Caso D · Proyecto libre existente que se adopta

Para un proyecto ya en marcha construido con el sistema anterior. Se conserva todo — stack, arquitectura, código, historial — y se le añade la capa de especificación trazada.

| Paso | Prompt | Agente | Produce |
|---|---|---|---|
| 1 | `01A-adopcion-gemini.md` | Gemini | `SPEC.md` reconstruido, ADR-002, `TESTING_STRATEGY.md`, `docs/plan-adopcion.md` |
| 2 | `01B-adopcion-claude.md` | Claude | `verify`, suite anotada con IDs, tests descartados eliminados |
| 3 | `04-revision-gemini.md` | Gemini | primera auditoría bajo el sistema nuevo |

**Compuerta previa.** La Etapa 0 del paso 1 recomienda **adoptar o regenerar**. En proyectos pequeños, regenerar desde `01-descubrimiento-gemini.md` suele ser más barato y deja una historia coherente desde el primer commit.

**Lo que la adopción revela.** Al mapear cada test contra una regla, los que no mapean son los rebuscados. Es el único punto del sistema donde ese problema se vuelve visible de golpe en vez de acumularse.

**Dos concesiones declaradas, no fingidas.** La evidencia de tests-antes-que-código rige desde el commit de adopción hacia adelante, y se marca una línea de corte en el `README` para que el auditor no reporte hallazgos falsos sobre el pasado. Y el umbral de mutación se mide antes de fijarse: un umbral aspiracional que falla el primer día termina desactivado.

**Cuarentena.** Los tests que no se pueden mapear de inmediato llevan `spec: PENDIENTE`. `verify` los cuenta y ese número nunca puede subir. Es deuda declarada y decreciente, no deuda oculta.

---

## 5 · Propiedad de archivos

La separación de poderes ya no depende de quién tiene acceso —ambos lo tienen a todo— sino de una regla explícita en cada prompt: **tener permiso de escritura no es autorización para usarlo.**

| Archivo | Escribe | Nunca toca |
|---|---|---|
| `SPEC.md` | Gemini, tras aprobación | Claude |
| ADR-001, ADR-002 | Gemini, tras aprobación | Claude |
| `TESTING_STRATEGY.md` | Gemini, tras aprobación | Claude |
| `docs/delta-actual.md` | Gemini | Claude solo lee |
| `docs/BENCHMARKING.md` | Gemini (1-M) | Claude solo lee |
| `README.md`, `CHANGELOG.md` | Claude | — |
| `verify`, código, tests | Claude | Gemini |

`docs/delta-actual.md` es transitorio y se sobreescribe en cada cambio. A diferencia de `agent_bridge.md`, tiene un lector definido: el implementador del bucle de cambios.

**Único paso manual que queda:** aprobar. Ya no transcribes nada.

---

## 8 · Obsoletos

Eliminar del ecosistema:

| Archivo | Motivo |
|---|---|
| `1. Ideas GEMINI` | Reemplazado por Descubrimiento |
| `2. Arquitectura GEMINI` | Reemplazado por Arquitectura |
| `3. Prototipo CLAUDE` | Era un implementador de migración instanciado con el VRP, no una plantilla |
| `Migrar GEMINI` | Fusionado en 1-M |
| `Investigar Repo` | Fusionado en 1-M |
| `Ideas_Nuevas` Gemini y Claude | Reemplazados |
| `Auditoria de roles` | Reemplazado |
| `5.x Repinta` | Reemplazado |

Se conservan con ediciones puntuales: `4 Revisa`, `5 Pinta`, `6 Sube`, `7 Empaqueta`, `8 Envío Cliente`.

Desaparece por completo: `agent_bridge.md`. Con acceso a carpeta ya sería escribible, pero sigue siendo redundante — `SPEC.md`, `CHANGELOG.md` y los ADRs cubren la memoria del sistema.

---

## 6 · Convención de commits

El historial no es higiene: es la evidencia que audita el sistema. De ahí las reglas.

| Momento | Mensaje | Estado de la suite |
|---|---|---|
| Gemini escribe especificación | `spec: [IDs] — [qué cambió]` | — |
| Gemini escribe arquitectura | `adr: [decisión]` | — |
| Claude levanta el andamiaje | `chore: andamiaje inicial` | sin tests |
| Claude escribe tests | `test: [IDs] — suite en rojo` | **roja, a propósito** |
| Claude implementa | `feat: [IDs] — implementación` | verde |
| Claude corrige un bug | `fix: [ID] — [descripción]` | verde |
| Claude cierra | `chore: [qué cierra]` | verde |

**Tres reglas duras:**

1. **Los tests van siempre en un commit anterior al del código que los satisface.** Es lo que hace comprobable el mandato de TDD, que hasta ahora era una declaración sin evidencia.
2. **El historial no se reescribe.** Nada de amend, rebase, squash ni force. Un historial editable no prueba nada: si el implementador puede reordenarlo, la comprobación del auditor se vuelve decorativa.
3. **Documentación y código no se mezclan en un commit.** La historia de `SPEC.md` es el registro de cuándo nació y cuándo se retiró cada regla, y se pierde si va enterrada en commits de implementación.
4. **Ningún agente figura como co-autor.** Ni Claude ni Gemini aparecen en `Co-Authored-By` ni en ninguna otra forma de atribución. Es coherente con la regla de procedencia: si no entra código que no puedas explicar, entonces el código es tuyo y el historial debe decirlo. La transparencia sobre el método vive en los ADRs y el README, que es donde corresponde.

---

## 7 · Pendiente

- **Anexo por stack:** herramientas concretas de trazabilidad, mutación y frontera. Requiere un lenguaje elegido.
- **Prompt de entrega académica:** rúbrica, artefactos del curso y preparación de defensa.
