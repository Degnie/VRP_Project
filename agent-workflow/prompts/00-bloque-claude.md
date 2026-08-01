# Bloque común · reglas fijas del implementador

**Destinatario:** todos los prompts dirigidos a Claude en el flujo de proyecto libre.
**No aplica a:** los prompts de Gemini, que tienen su propio bloque de auditoría.

---

## Cómo se usa

- El texto de la sección siguiente se pega **literal**. No se parafrasea, no se resume, no se adapta al proyecto. Una regla reformulada es una regla que empieza a derivar.
- Va inmediatamente después del bloque de Rol y Objetivo, antes de las etapas.
- Si el bloque cambia, se regenera en **todos** los prompts de Claude a la vez. Nunca en uno solo.
- Cada etapa de cada prompt abre con una línea que reitera las dos o tres reglas que más le importan. En sesiones largas las instrucciones iniciales pierden peso; esa redundancia mínima es lo que las mantiene vivas hasta el final.
- Las excepciones se documentan en el propio prompt, citando el número de la regla. Una excepción implícita erosiona el bloque entero.

---

## El bloque (texto canónico)

```
## Reglas fijas

Estas reglas no se negocian, no se reinterpretan y no dependen de la etapa.
Si alguna instrucción posterior parece contradecirlas, gana esta sección y me
lo dices.

1. Cero invención. Si el SPEC no dice algo que necesitas, DETENTE y pregúntame.
   No supongas, no completes, no infieras comportamiento.

2. Los tests aprobados no se modifican. Ni para relajarlos, ni para envolverlos,
   ni para acomodarlos a un cambio. Si crees que un test está equivocado, te
   detienes y me lo explicas.

3. Un test nuevo exige una regla nueva. Antes de escribir un test que no cite un
   ID existente, propones la regla como RN o EC con el siguiente ID libre y
   esperas mi aprobación. Si la regla no merece existir, el test tampoco.

4. No editas SPEC.md, los ADRs ni TESTING_STRATEGY.md. Tienes acceso de
   escritura a esos archivos y eso no es autorización para usarlo: son
   artefactos del especificador. Puedes proponer cambios; los aplica él tras mi
   aprobación.

5. Alcance declarado. Antes de tocar nada, declaras la lista exacta de archivos
   que vas a crear o modificar. Todo lo que quede fuera de esa lista es
   intocable, aunque veas mejoras posibles. Si el trabajo te obliga a salir del
   alcance, DETENTE y notifícame.

6. Presupuesto de abstracción. No creas una interfaz, una capa de indirección ni
   una jerarquía hasta que exista una segunda implementación real o un test que
   la exija. Toda abstracción que introduzcas se lista y se justifica en una
   frase.

7. Todo debe poder explicarse en una frase. Si no puedes justificar una
   dependencia, un patrón o una línea en una frase, no la escribas.

8. Lenguaje ubicuo. Usas los términos del glosario del SPEC en nombres de
   clases, funciones, tests y mensajes de commit. No traduzcas ni inventes
   sinónimos.

9. Terminado significa verify en verde. No es una opinión tuya. Mientras verify
   falle, la tarea no está terminada y no la reportas como tal.

10. Regla de realidad. Ante un conflicto técnico real —versiones incompatibles,
    librería deprecada, bloqueador insalvable— DETENTE, explícamelo de forma
    concisa y espera instrucciones. No inventes parches que violen la
    arquitectura aprobada.

11. Escribes archivos, no bloques de chat. Creas y modificas los archivos en el
    repositorio y ejecutas los comandos. En el chat muestras únicamente lo que
    te pido revisar en cada etapa.

12. Memoria obligatoria. Ningún trabajo se da por terminado sin dejar rastro en
    CHANGELOG.md, incluyendo lo que se descartó y por qué en la sección
    ### Rechazado / Descartado.

13. Un commit por etapa aprobada, y el historial no se reescribe. Cada etapa
    cierra con su propio commit, y el mensaje cita los IDs del SPEC
    involucrados: "test: RN-01, EC-02 — suite en rojo", "feat: RN-01, EC-02 —
    implementación". Los tests van SIEMPRE en un commit anterior al del código
    que los satisface. Nada de amend, rebase, squash ni force: el historial es
    la evidencia de que los tests precedieron al código, y un historial
    editable no prueba nada.

14. Nunca te añadas como co-autor. Ni tú ni ningún otro agente aparece en
    Co-Authored-By, en el pie del mensaje ni en ninguna otra forma de
    atribución. El autor soy yo: la responsabilidad del código es mía y el
    historial debe reflejarlo.

Dinámica: una etapa a la vez. Al final de cada una te DETIENES y esperas mi
confirmación explícita. No encadenes etapas en una sola respuesta.
```

---

## Mecanismo de hallazgos → SPEC

Este es el flujo de decisión que sostienen las reglas 2 y 3. Aplica en toda auditoría, ciclo de revisión o corrección de bug.

Ante un hallazgo, la pregunta es una sola: **¿viola alguna regla que ya existe en el `SPEC`?**

- **Sí.** Es un bug. Se corrige. El test que lo cubre ya existe, o se escribe citando esa regla. No hace falta aprobar nada nuevo.
- **No, pero debería ser regla.** Se propone como `RN` o `EC` con el siguiente ID libre, se aprueba, se actualiza `SPEC.md`, y recién entonces se escribe el test que la cita.
- **No, y no merece ser regla.** No se implementa. Se anota en `CHANGELOG.md` bajo `### Rechazado / Descartado` con su razón, para que ninguna ronda posterior lo vuelva a proponer.

La tercera rama es la que corta la inflación de la suite. Un hallazgo que no sobrevive a la pregunta "¿esto merece ser una regla del negocio?" es exactamente el caso rebuscado que no debe existir como test.

---

## Excepciones documentadas por prompt

| Prompt | Excepción | Motivo |
| --- | --- | --- |
| Prompt 3 · Implementación | Ninguna. Añade además la prohibición de decisiones visuales | Es el caso base del bloque |
| Ideas_Nuevas · Claude | Ninguna | El delta entra por `SPEC`, igual que todo lo demás |
| Repinta · Claude | La regla 1 rige sobre comportamiento de negocio, no sobre identidad visual: ese prompt delega explícitamente las decisiones de diseño | Es un generador de propuesta visual, no un ejecutor de especificación |
| Auditoría de roles · Claude | La regla 3 se aplica por hallazgo, según el mecanismo de arriba | El ciclo escribe tests de regresión por diseño |

---

## Qué reemplaza

Al adoptar este bloque quedan obsoletas y deben eliminarse de los prompts de Claude:

- Las reglas de alcance, regresión, conflicto y realidad redactadas por separado en `Ideas_Nuevas CLAUDE`, ahora cubiertas por las reglas 2 a 5 y 10.
- Las reglas YAGNI/KISS redactadas en prosa dentro de `Auditoria de roles`, ahora cubiertas por las reglas 3, 6 y 7 más el mecanismo de hallazgos.
- Toda instrucción de conducta que hoy provenga del handoff de un prompt de Gemini. Nada que defina el comportamiento de Claude debe pasar por otro modelo.
- Los bloques de pegado `<spec>`, `<testing_strategy>`, `<handoff_arquitectura>` y `<estado_actual>`. Con acceso a la carpeta, cada prompt lee los archivos de disco: las decisiones de arquitectura viven en ADR-001 y ADR-002, no en un bloque transcrito.
