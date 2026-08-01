# Especificación · [NOMBRE DEL PROYECTO]

**Etiqueta:** [PROYECTO LIBRE]
**Versión de la spec:** 1.0
**Estado:** borrador
**Última actualización:** AAAA-MM-DD

---

## Contrato de este archivo

Estas cuatro reglas gobiernan todo el proyecto. No son sugerencias.

1. **Ningún test sin ID.** Todo test declara la regla que verifica mediante el comentario `spec: RN-04`. Un test que no cita un ID de este archivo no entra al repositorio.
2. **Ninguna regla sin test.** Toda `RN`, `CU` y `EC` activa debe tener al menos un test que la cite. Las `RNF` se excluyen: se verifican con medición, no con la suite.
3. **Los IDs son inmutables.** No se reutilizan, no se renumeran, no se reciclan. Una regla eliminada baja a §9 con su motivo.
4. **Este archivo lo escribe el especificador, nunca el implementador.** Quien escribe código y tests tiene acceso de escritura y no lo usa: si cree que una regla está equivocada o falta, se detiene y lo propone. Cambiar un test exige cambiar antes la regla que lo origina, y esa edición se aprueba antes de aplicarse.

**Convención de referencia en tests.** El ID va en un comentario en la línea previa a la declaración del test, o dentro de su docstring. Es lo único obligatorio; incluir el ID también en el nombre del test es opcional pero recomendable, porque así el fallo nombra la regla.

```
# spec: RN-01
def test_capacidad_no_se_excede():
    ...

# spec: RN-01, EC-07
def test_capacidad_con_carga_fraccionada():
    ...
```

---

## 0 · Glosario (lenguaje ubicuo)

Los términos que aparecen aquí son los únicos que se usan en código, tests, commits y documentación. Si el cliente lo llama "reserva", no se llama `booking` en el modelo.

| Término | Significado en este dominio | Qué NO es |
| --- | --- | --- |
| Reserva | Compromiso de un asiento para una función concreta, con vencimiento | No es una compra; una reserva vencida no genera cobro |
| Función | Proyección de una obra en fecha y sala determinadas | No es la obra; una obra tiene muchas funciones |
| [término] | [significado] | [confusión que hay que evitar] |

---

## 1 · Resumen del negocio

Tres a cinco líneas. Qué problema resuelve el sistema y para quién. Sin jerga técnica.

> [Proviene de la Fase 1 del prompt de descubrimiento.]

---

## 2 · Eventos de dominio

Lo que ocurre en el negocio, en orden temporal, en pasado. Se escribe **antes** de nombrar entidades: los eventos revelan el modelo, no al revés.

1. Función programada
2. Reserva creada
3. Reserva confirmada
4. Reserva vencida
5. Asientos liberados

Los eventos no llevan ID. Si un evento debe garantizarse, se convierte en una regla de §4.

---

## 3 · Modelo de dominio

Una entrada por entidad. Sin diagramas y sin decisiones de persistencia: aquí no se menciona ninguna base de datos, tabla ni colección.

### Reserva

- **Qué sabe:** identificador, función asociada, asientos, estado, instante de vencimiento
- **Qué hace:** se confirma, se cancela, vence
- **Con qué se relaciona:** pertenece a una Función; agrupa uno o más Asientos
- **Reglas que la gobiernan:** RN-01, RN-03

### [Entidad]

- **Qué sabe:**
- **Qué hace:**
- **Con qué se relaciona:**
- **Reglas que la gobiernan:**

---

## 4 · Reglas de negocio e invariantes (RN)

Cosas que son verdad siempre. Si el sistema puede violarlas aunque sea un instante, no son invariantes: son validaciones y van como escenario en §5.

### RN-01 · Una reserva vencida no puede confirmarse

- **Estado:** activa
- **Enunciado:** si el instante actual supera el vencimiento de la reserva, la confirmación es imposible.
- **Ejemplo válido:** reserva creada 08:00, vence 08:15, se confirma 08:07.
- **Ejemplo inválido:** reserva creada 08:00, vence 08:15, se intenta confirmar 08:16.
- **Al violarse:** la operación se rechaza con error `ReservaVencida`. No se cobra, no se modifica el estado.

### RN-02 · [Enunciado corto en una línea]

- **Estado:** activa
- **Enunciado:**
- **Ejemplo válido:**
- **Ejemplo inválido:**
- **Al violarse:**

---

## 5 · Escenarios de aceptación (CU)

Comportamiento observable del sistema, en Dado-Cuando-Entonces. Solo la frontera de aceptación: no se escribe Gherkin para funciones internas.

### CU-01 · Confirmar una reserva vigente

- **Estado:** activa
- **Dado** una reserva en estado pendiente cuyo vencimiento no ha pasado
- **Cuando** el usuario la confirma
- **Entonces** la reserva pasa a confirmada y los asientos quedan asignados de forma definitiva
- **Reglas involucradas:** RN-01, RN-03

### CU-02 · [Título]

- **Estado:** activa
- **Dado**
- **Cuando**
- **Entonces**
- **Reglas involucradas:**

---

## 6 · Casos límite (EC)

Fallos, concurrencia, interrupciones y datos en la frontera. Un caso límite que no está aquí **no se implementa y no se prueba**.

### EC-01 · Dos confirmaciones simultáneas del último asiento

- **Estado:** activa
- **Situación:** dos usuarios confirman reservas distintas sobre el mismo asiento en el mismo instante.
- **Comportamiento esperado:** exactamente una confirmación tiene éxito; la otra se rechaza con `AsientoNoDisponible`. No existe estado en que el asiento quede doblemente asignado.
- **Regla que lo gobierna:** RN-03

### EC-02 · [Título]

- **Estado:** activa
- **Situación:**
- **Comportamiento esperado:**
- **Regla que lo gobierna:** [ID, o "ninguna — este caso define su propia regla"]

---

## 7 · Requisitos no funcionales (RNF)

Cada uno lleva número. Un requisito sin medida no es un requisito: es un adjetivo.

### RNF-01 · Latencia de consulta de disponibilidad bajo carga

- **Estado:** activa
- **Estímulo:** 200 consultas concurrentes de disponibilidad
- **Respuesta esperada:** todas responden sin error
- **Medida:** p95 por debajo de 400 ms
- **Cómo se verifica:** benchmark manual, no automatizado todavía

### RNF-02 · [Título]

- **Estado:** activa
- **Estímulo:**
- **Respuesta esperada:**
- **Medida:**
- **Cómo se verifica:**

---

## 8 · Fuera de alcance

Lo que este proyecto **no** hace, con su razón. Si el agente propone algo de esta lista, la respuesta es no y no se discute. Para sacar algo de aquí hace falta una decisión explícita registrada como ADR.

| Descartado | Razón |
| --- | --- |
| Pagos en línea | El MVP reserva, no cobra |
| Notificaciones push | El correo cubre la necesidad a esta escala |
| [elemento] | [razón] |

---

## 9 · IDs retirados

Los IDs de esta tabla no vuelven a usarse. Un test que cite uno de ellos está obsoleto y debe eliminarse.

| ID | Motivo del retiro | Reemplazado por | Fecha |
| --- | --- | --- | --- |
| RN-07 | La regla resultó ser una validación, no una invariante | CU-09 | AAAA-MM-DD |
