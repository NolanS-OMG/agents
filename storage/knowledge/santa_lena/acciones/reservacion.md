---
slug: acciones/reservacion
doc_type: accion
title: Reservación
description: Registra una reservación de mesa en el restaurante.
tags:
- accion
- reservacion
status: stable
campos_requeridos: []
campos_opcionales: []
confirmacion_requerida: false
---

# Reservación

## Campos requeridos

| Campo | Descripción |
|-------|-------------|
| nombre_cliente | Nombre de la reservación |
| telefono | Teléfono de contacto |
| fecha | Fecha de la reservación |
| hora | Hora deseada |
| numero_personas | Cuántas personas asistirán |

## Campos opcionales

| Campo | Descripción |
|-------|-------------|
| ocasion_especial | Cumpleaños, aniversario, etc. |
| preferencia_zona | Jardín, interior |
| notas_especiales | Silla para bebé, necesidades especiales |

## Confirmación

Se requiere confirmación explícita del cliente antes de procesar.