---
type: Acción
title: Reservación
description: Registra una reservación de mesa en el restaurante.
tags: [accion, reservacion]
generated: { by: human:nolan, at: 2026-07-25T12:00:00Z }
status: stable
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
