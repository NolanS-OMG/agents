---
slug: acciones/mostrar-proyectos
doc_type: accion
title: Mostrar Proyectos
description: Muestra cards de proyectos en el chat
tags:
- proyectos
- frontend
status: stable
campos_requeridos: []
campos_opcionales:
- filter
- projectIds
confirmacion_requerida: false
channels:
- web
frontend_action: true
---

Muestra una galería de proyectos en el chat.
Si se especifica filter, muestra solo los que matchean por tech/titulo.
Sin parámetros muestra los más destacados.
