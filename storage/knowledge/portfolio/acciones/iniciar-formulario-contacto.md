---
slug: acciones/iniciar-formulario-contacto
doc_type: accion
title: Iniciar Formulario de Contacto
description: Inicia flujo de formulario para enviar mensaje a Nolan
tags:
- contacto
- formulario
- frontend
status: stable
campos_requeridos: []
campos_opcionales:
- name
- email
- message
confirmacion_requerida: false
channels:
- web
frontend_action: true
---

Inicia un flujo interactivo de formulario dentro del chat para enviar un mensaje a Nolan.
Si el AI ya conoce el nombre o email del usuario, los pasa como pre-fill.
