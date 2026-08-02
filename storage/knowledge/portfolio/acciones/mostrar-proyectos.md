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
- ids
confirmacion_requerida: false
channels:
- web
frontend_action: true
frontend_tool: show_projects
---

Muestra tarjetas de proyectos en el chat.
ids: array de IDs de proyectos a mostrar. Si vacío, muestra todos.
IDs válidos: snake-rl, schools, inventory-crud, portfolios-lobby.
