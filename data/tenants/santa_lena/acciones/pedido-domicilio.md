---
type: Acción
title: Pedido a Domicilio
description: Registra un pedido para entrega a domicilio.
tags: [accion, pedido, domicilio]
generated: { by: human:nolan, at: 2026-07-25T12:00:00Z }
status: stable
---

# Pedido a Domicilio

## Campos requeridos

| Campo | Descripción |
|-------|-------------|
| nombre_cliente | Nombre de quien recibe |
| telefono | Teléfono de contacto |
| direccion_entrega | Dirección completa de entrega |
| items_pedido | Lista de platillos con cantidades |

## Campos opcionales

| Campo | Descripción |
|-------|-------------|
| notas_especiales | Alergias, sustituciones, indicaciones de entrega |
| metodo_pago | Efectivo o tarjeta |

## Confirmación

Se requiere confirmación explícita del cliente antes de procesar.
