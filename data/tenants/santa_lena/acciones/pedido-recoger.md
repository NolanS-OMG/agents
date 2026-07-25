---
type: Acción
title: Pedido para Recoger
description: Registra un pedido para recoger en el restaurante.
tags: [accion, pedido, recoger]
generated: { by: human:nolan, at: 2026-07-25T12:00:00Z }
status: stable
---

# Pedido para Recoger

## Campos requeridos

| Campo | Descripción |
|-------|-------------|
| nombre_cliente | Nombre de quien recoge |
| telefono | Teléfono de contacto |
| items_pedido | Lista de platillos con cantidades |

## Campos opcionales

| Campo | Descripción |
|-------|-------------|
| hora_recoger | Hora aproximada de llegada |
| notas_especiales | Alergias, sustituciones |

## Confirmación

Se requiere confirmación explícita del cliente antes de procesar.
