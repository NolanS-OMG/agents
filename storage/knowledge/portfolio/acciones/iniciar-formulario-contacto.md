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
frontend_tool: send_message
---

Inyecta formulario de contacto en el chat para enviar mensaje a Nolan.
name, email, message: campos pre-llenados si el AI los conoce.
