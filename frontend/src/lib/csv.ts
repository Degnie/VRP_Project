// Parser RFC 4180: procesa el texto completo carácter por carácter en vez de
// hacer un split por línea antes de leer comillas — un split previo (como
// tenía esta función antes) corta a mitad de un campo entrecomillado que
// contiene un salto de línea real (ej. una dirección larga en varias líneas
// dentro de "..."), truncando esa fila y generando una fila fantasma con el
// resto, que termina descartada como "datos inválidos" (bug real: la app no
// podía reimportar su propio export si algún campo tenía un salto de línea).
// Excel en configuración regional es-* (es-PE, es-ES, etc.) exporta CSV con
// ";" como separador de columnas (usa "," como separador decimal) — sin
// detectarlo, cada fila entra como una sola celda y ninguna columna matchea,
// dando "el archivo no tiene filas válidas" cuando el archivo en realidad
// tiene datos válidos con el delimitador equivocado. Se cuenta ";" vs ","
// en la primera línea (fuera de comillas) para decidir cuál usar.
function detectDelimiter(text: string): "," | ";" {
  const firstLine = text.split(/\r?\n/, 1)[0] ?? "";
  let commas = 0;
  let semicolons = 0;
  let inQuotes = false;
  for (const char of firstLine) {
    if (char === '"') inQuotes = !inQuotes;
    else if (!inQuotes && char === ",") commas++;
    else if (!inQuotes && char === ";") semicolons++;
  }
  return semicolons > commas ? ";" : ",";
}

// Bug real: `Blob.text()` decodifica siempre como UTF-8 (spec WHATWG), sin
// sniffear encoding — un CSV real en Latin-1/Windows-1252 (típico de un
// Excel guardado como "CSV" en Windows con configuración regional es-*)
// producía caracteres corruptos en nombre/dirección de cliente y de
// vehículo, con el import reportando éxito igual, sin ningún aviso.
//
// Dos intentos anteriores fallaron (Ronda 44):
// - Contar apariciones de "�" (carácter de reemplazo U+FFFD) sin más: un
//   archivo UTF-8 legítimo con un solo "�" como dato real se corrompía por
//   un reintento innecesario.
// - Exigir una PROPORCIÓN mínima de "�" sobre el total de caracteres: un
//   archivo grande (cientos de filas) en Windows-1252 real, con solo 2-3
//   nombres acentuados, diluye esa proporción por debajo de cualquier
//   umbral fijo — esas pocas tildes quedaban corruptas sin activar el
//   fallback, reproduciendo el bug original a partir de cierto tamaño.
//
// Señal correcta: `TextDecoder("utf-8", {fatal: true})` LANZA si el buffer
// contiene una secuencia de bytes que no es UTF-8 válido — que es
// exactamente lo que pasa con texto Windows-1252 real (los bytes 0x80-0xFF
// de una tilde/ñ casi nunca forman una secuencia de continuación UTF-8
// válida). Un archivo genuinamente UTF-8 con un "�" como dato real SÍ es
// UTF-8 válido (ese carácter tiene su propia codificación de 3 bytes
// perfectamente válida) y no dispara la excepción — se distingue "byte
// corrupto/mal codificado" de "el carácter de reemplazo es el dato real"
// sin depender de contar apariciones ni de ningún umbral por tamaño.
export async function decodeCsvFile(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  if (bytes.length >= 2 && ((bytes[0] === 0xff && bytes[1] === 0xfe) || (bytes[0] === 0xfe && bytes[1] === 0xff))) {
    return new TextDecoder("utf-16" + (bytes[0] === 0xff ? "le" : "be")).decode(buffer);
  }
  // Bug real (Ronda 46, confirmación): un CSV "UTF-8 con BOM" que además
  // tenga alguna celda en bytes Windows-1252 (mixed encoding, típico de un
  // export de Excel con una celda pegada de otra fuente) dispara el fallback
  // de abajo — pero `TextDecoder("windows-1252")` no sabe reconocer/descartar
  // el BOM UTF-8 (EF BB BF), solo aplica a encodings Unicode (utf-8/utf-16),
  // así que esos 3 bytes se decodifican como los caracteres literales "ï»¿"
  // pegados al primer header, rompiendo la detección de columnas por nombre.
  // Se descarta el BOM UTF-8 del buffer ANTES de cualquiera de los dos
  // intentos, para que el fallback windows-1252 nunca lo vea.
  const hasUtf8Bom = bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf;
  const content = hasUtf8Bom ? buffer.slice(3) : buffer;
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(content);
  } catch {
    return new TextDecoder("windows-1252").decode(content);
  }
}

export function parseCsvText(text: string): string[][] {
  const delimiter = detectDelimiter(text);
  const rows: string[][] = [];
  let row: string[] = [];
  let current = "";
  let inQuotes = false;
  let i = 0;

  const pushCell = () => {
    row.push(current.trim());
    current = "";
  };
  const pushRow = () => {
    pushCell();
    rows.push(row);
    row = [];
  };

  while (i < text.length) {
    const char = text[i];
    if (inQuotes) {
      if (char === '"' && text[i + 1] === '"') {
        current += '"';
        i += 2;
        continue;
      }
      if (char === '"') {
        inQuotes = false;
        i++;
        continue;
      }
      current += char;
      i++;
      continue;
    }

    if (char === '"') {
      inQuotes = true;
      i++;
    } else if (char === delimiter) {
      pushCell();
      i++;
    } else if (char === "\r") {
      i++;
    } else if (char === "\n") {
      pushRow();
      i++;
    } else {
      current += char;
      i++;
    }
  }
  // Última fila sin salto de línea final.
  if (current !== "" || row.length > 0) pushRow();

  return rows.filter((r) => !(r.length === 1 && r[0] === ""));
}
