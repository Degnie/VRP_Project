<delta_aprobado>
  <resumen>
    Fase 3 de 3: descarga real del CSV de reprogramados de la cuenta.
    La Fase 2 ya cubrió el CSV en disco, el conteo/detalle vía
    GET /reprogramados/pending y el merge automático vía
    POST /reprogramados/merge — lo único pendiente es exponer el archivo
    tal cual para que el dueño pueda descargarlo y abrirlo en Excel/hoja de
    cálculo, fuera de la app. No se agrega import (subir un CSV editado a
    mano) — el usuario confirmó que no hace falta, el flujo de edición ya
    pasa por la app (PATCH /clients/{id} antes de reprogramar).
  </resumen>
  <clasificacion> aditiva </clasificacion>
  <ids_nuevos>
    - RN-035 (Reprogramación - Descarga CSV): GET /reprogramados/export.csv
      sirve el archivo `reprogramados_{account_id}.csv` de la cuenta
      autenticada tal cual está en disco (Content-Type text/csv,
      Content-Disposition attachment), mismo patrón que
      GET /solutions/{id}/export.pdf. Si la cuenta no tiene reprogramados
      pendientes, responde 404 en vez de un CSV vacío con 200 (mismo
      criterio que RN-EXP-002).
  </ids_nuevos>
  <ids_modificados> ninguno </ids_modificados>
  <ids_retirados> ninguno </ids_retirados>
  <decision_adr> ninguno </decision_adr>
  <spec_version> v1.8 </spec_version>
</delta_aprobado>
