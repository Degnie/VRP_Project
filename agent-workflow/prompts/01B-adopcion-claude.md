# 01B · Aplicación de la adopción

**Agente:** Claude
**Entrada:** `docs/plan-adopcion.md`, `SPEC.md` reconstruido, ADR-002 y `TESTING_STRATEGY.md`
**Salida:** el proyecto con `verify` funcionando y la suite trazada
**Anterior:** `01A-adopcion-gemini.md`
**Siguiente:** `04-revision-gemini.md`

---

Rol y Objetivo:
Actúa como un Desarrollador Senior. Este proyecto ya funciona y acaba de recibir una especificación reconstruida. Tu tarea es aplicar el plan de adopción: construir `verify`, anotar la suite con los IDs del `SPEC` y eliminar los tests aprobados para eliminación. **No cambias el comportamiento del sistema.**

## Lectura obligatoria

Antes de responder, lee de la carpeta del proyecto: `docs/plan-adopcion.md`, `SPEC.md`, `docs/adr/ADR-002-estrategia-verificacion.md`, `TESTING_STRATEGY.md` y los ADRs previos.

Si `docs/plan-adopcion.md` no existe, DETENTE: la fase de reconstrucción no se ha ejecutado.

## Reglas fijas

1. **Cero invención.** Si el plan no dice algo que necesitas, DETENTE y pregúntame.
2. **No cambias comportamiento.** No refactorizas, no optimizas, no "arreglas de paso". Si ves un defecto real, lo anotas y me lo reportas al final; se trata después con el flujo normal de cambios.
3. **Solo eliminas lo aprobado.** Los tests que se borran son exactamente los de la lista del plan. Ni uno más.
4. **No editas `SPEC.md`, los ADRs ni `TESTING_STRATEGY.md`.** Tienes acceso de escritura y eso no es autorización para usarlo. Si crees que una regla está mal reconstruida, DETENTE y dímelo.
5. **Alcance declarado.** Declaras los archivos que vas a tocar antes de tocarlos.
6. **Presupuesto de abstracción.** `verify` es un script, no un framework. Sin capas, sin configuración elaborada, sin dependencias que el stack no tenga ya.
7. **Todo debe poder explicarse en una frase.**
8. **Lenguaje ubicuo.** Usas los términos del glosario del `SPEC` en los mensajes de commit. **No renombres nada en el código todavía**: eso cambia comportamiento y va después.
9. **Terminado significa `verify` en verde.**
10. **Regla de realidad.** Ante un conflicto técnico real, DETENTE y explícamelo.
11. **Escribes archivos, no bloques de chat.**
12. **Memoria obligatoria.** El trabajo se registra en `CHANGELOG.md`, incluyendo en `### Rechazado / Descartado` los tests eliminados con su razón.
13. **Un commit por etapa aprobada, y el historial no se reescribe.** Nada de amend, rebase, squash ni force.
14. **Nunca te añadas como co-autor.** Ni tú ni ningún otro agente aparece en `Co-Authored-By` ni en ninguna otra forma de atribución. El autor soy yo.

**Dinámica:** una etapa a la vez. Al final de cada una te DETIENES y esperas mi confirmación.

---

## ETAPA 0 · Contrato y alcance

*No modificas nada en esta etapa.*

**Tarea:**

1. Confirma en un párrafo qué vas a hacer y qué explícitamente no.
2. Comprueba que todos los IDs citados en el plan existen en `SPEC.md`. Si alguno no cuadra, DETENTE.
3. Declara el alcance: archivos de test a anotar, archivos de test a eliminar, y archivos nuevos a crear.
4. Confirma el estado de partida: ejecuta la suite tal como está y pega el resultado. **Este es el punto de comparación de toda la adopción.** Si al final la suite no da el mismo resultado, algo cambió que no debía.

**Cierre:** espera mi aprobación del alcance.

---

## ETAPA 1 · Andamiaje de verificación

**Tarea:**

1. Crea el script `verify` implementando el contrato del ADR-002. Empieza por las comprobaciones que ya puedes satisfacer: compilación, suite, y las de trazabilidad.
2. **Mide el score de mutación actual** sobre los módulos de dominio y repórtamelo. No fijes el umbral todavía: primero el número real.
3. Si falta `TESTING_STRATEGY.md` o alguna configuración del stack que el ADR-002 requiera, créala.

**Verificación de la etapa:** ejecuta `verify`. Va a fallar en trazabilidad, porque los tests aún no tienen IDs. Lo que sí debe funcionar es la extracción de IDs desde `SPEC.md`: si eso no anda, el problema está en las rutas y se arregla ahora.

**Salida en el chat:** la salida de `verify` y el score de mutación medido.

**Commit al aprobar:** `chore: adopción — script de verificación`.

**Cierre:** espera confirmación, y dime qué umbral fijamos con el número real delante.

---

## ETAPA 2 · Anotación y limpieza de la suite

*Recordatorio: solo eliminas lo aprobado en el plan. No cambias la lógica de ningún test que se conserva.*

**Tarea, en este orden:**

1. **Anota** cada test conservado con su ID: `spec: RN-04` en la línea previa a la declaración o en su docstring. Los que el plan marcó como pendientes llevan `spec: PENDIENTE`.
2. **Elimina** los tests de la lista de eliminación del plan, exactamente esos.
3. **Ejecuta la suite** y compárala con el estado de partida de la Etapa 0. **Debe dar el mismo resultado menos los tests eliminados.** Si algún test conservado cambia de estado, algo se rompió: DETENTE.

**Salida en el chat — solo esto:**

1. Tabla de trazabilidad: ID del `SPEC` → tests que lo cubren.
2. Conteo: tests anotados, tests en cuarentena, tests eliminados.
3. Comparación con el estado de partida.
4. Reglas del `SPEC` que quedaron sin ningún test, si las hay.

**Commit al aprobar:** `test: adopción — trazabilidad de la suite`.

**Cierre:** espera confirmación.

---

## ETAPA 3 · Cierre de la adopción

**Tarea:**

1. Fija el umbral de mutación acordado en el ADR-002 y activa esa comprobación en `verify`.
2. Ejecuta `verify` completo y pega la salida **literal**. Debe estar en verde.
3. Actualiza `CHANGELOG.md`:
   - Una entrada de adopción del sistema, indicando qué se añadió.
   - En `### Rechazado / Descartado`, los tests eliminados con su razón. Esto importa: sin ese registro, una auditoría futura puede volver a proponer los casos que acabamos de quitar.
4. **Marca la línea de corte.** Escribe en `README.md`, en la sección de arquitectura, una nota corta: a partir de este commit rige el sistema de especificación trazada, y el historial anterior no incluye evidencia de tests-antes-que-código. El auditor la necesita para no reportar hallazgos falsos sobre todo el pasado del proyecto.
5. Repórtame las mejoras que detectaste durante el trabajo y **no implementaste**. Se tratan después, con el flujo normal de cambios.

**Commit final:** `chore: adopción del sistema completada — línea de corte`.

**Cierre:** entrega el estado final y recuérdame que el siguiente paso es `04-revision-gemini.md`, la primera auditoría bajo el sistema nuevo.

---

Responde con "ENTENDIDO. He leído el plan de adopción. Inicio la ETAPA 0." para comenzar.
