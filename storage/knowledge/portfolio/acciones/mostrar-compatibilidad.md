---
slug: acciones/mostrar-compatibilidad
doc_type: accion
title: Mostrar Compatibilidad
description: Muestra dashboard de compatibilidad de skills
tags:
- skills
- compatibilidad
- frontend
status: stable
campos_requeridos:
- query
campos_opcionales:
- categories
confirmacion_requerida: false
channels:
- web
frontend_action: true
---

Evalúa la compatibilidad entre lo que busca el usuario y los skills de Nolan.
Renderiza un mini-dashboard con score y desglose por categoría.
query: descripción libre de lo que buscan.
categories: opcional, ya parseado por el AI en categorías.
