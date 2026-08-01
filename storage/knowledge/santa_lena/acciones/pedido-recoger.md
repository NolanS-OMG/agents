---
slug: acciones/pedido-recoger
doc_type: accion
title: Pedido para Recoger
description: Registra un pedido para recoger en el restaurante.
tags:
- accion
- pedido
- recoger
status: stable
campos_requeridos: []
campos_opcionales: []
confirmacion_requerida: false
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