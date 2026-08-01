---
slug: proyectos-destacados
doc_type: negocio
title: Proyectos Destacados
description: Portfolio de 4 proyectos principales desarrollados por Nolan Ashcraft
tags:
- proyectos
- portfolio
- casos de éxito
status: stable
---

# Proyectos Destacados

## 1. Inventory CRUD App (Aplicación ABCC)

**Estado:** ✅ Completado

### Stack Tecnológico
- Frontend: HTML5, CSS3, JavaScript (ES6+)
- Backend: Node.js, REST API Architecture
- Base de Datos: MySQL

### Descripción

Aplicación Web Full-Stack para la gestión de inventarios basada en el modelo ABCC (Altas, Bajas, Cambios y Consultas), desarrollada como prueba técnica de selección. Implementa una arquitectura desacoplada donde una interfaz web estática consume endpoints RESTful servidos por Node.js, procesando las operaciones sobre una base de datos relacional MySQL.

### Características Clave

- **Arquitectura Desacoplada (Decoupled Frontend/Backend)**: Frontend ligero estructurado en HTML/CSS/JS vainilla que realiza peticiones asíncronas a una API REST construida en Node.js
- **Manejo Idempotente y Robusto de SKUs**: Implementación de reglas de negocio centradas en la clave SKU (Stock Keeping Unit) como identificador único. El principal reto consistió en garantizar la consistencia relacional e idempotencia al actualizar registros de productos y sus jerarquías (Departamentos, Clases y Familias)
- **Validación de Datos en Dos Capas**: Validación estricta de entradas tanto en cliente para mejorar la experiencia de usuario (UX) como en el servidor para asegurar la integridad de la base de datos relacional

### Problema Resuelto

Gestión eficiente de inventarios con operaciones CRUD completas, garantizando consistencia de datos y experiencia de usuario fluida mediante validaciones en múltiples capas.

---

## 2. Portfolios Hub / Lobby Page

**Estado:** ✅ Completado  
**Link:** [nolanashcraft.netlify.app](https://nolanashcraft.netlify.app)

### Stack Tecnológico
- Frontend: HTML5, CSS3, JavaScript (ES6+)
- Despliegue: Netlify

### Descripción

Página de aterrizaje y portal centralizado (Lobby) diseñado para presentar la galería de portfolios web creados para clientes de diversos sectores (desarrolladores de software, artistas 3D/VFX, entre otros), así como una colección de plantillas preconfiguradas. Funciona además como plataforma de venta directa de servicios de desarrollo web freelance.

### Características Clave

- **Galería Interactiva y Showcase**: Organización estética y navegable de proyectos reales y plantillas creadas, destacando perfiles profesionales específicos con autorización de cliente
- **Landing Page de Conversión Freelance**: Integración de secciones informativas sobre la propuesta de valor, estructura de precios competitivos y entregables (sitios activos 24/7, soporte continuo y generación de códigos QR para CVs)
- **Optimización y Carga Ultra Rápida**: Desarrollo 100% en tecnologías web estándar (JS vainilla, CSS3) sin frameworks pesados ni dependencias de backend, maximizando el rendimiento de carga y SEO estático

### Problema Resuelto

Centralización de proyectos freelance y showcase profesional con rendimiento óptimo, sirviendo como herramienta de marketing y venta directa de servicios de desarrollo web.

---

## 3. Snake RL - AI vs Human

**Estado:** ✅ Completado

### Stack Tecnológico
- Frontend/Web: TypeScript, Next.js, Tailwind CSS
- Machine Learning/AI: Python, Gymnasium/Gym, Stable-Baselines3, PyTorch, TensorFlow
- Web Deployment/Inferencia: ONNX, ONNX Runtime Web

### Descripción

Aplicación interactiva que permite a los usuarios jugar de forma individual, competir en tiempo real contra un agente de Inteligencia Artificial o simplemente observar cómo toma decisiones en tiempo real. Entrenado mediante Aprendizaje por Refuerzo (Reinforcement Learning), todo el procesamiento e inferencia de la red neuronal se ejecuta directamente en el navegador cliente mediante ONNX Runtime Web, sin necesidad de servidores externos.

### Características Clave

- **Representación Matricial del Entorno (Observation Space)**: Modelado del mapa del juego como una matriz bidimensional con correspondencia exacta de píxeles/cuadros (0 = celda vacía, 1 = cuerpo/cabeza de la serpiente, 2 = fruta), permitiendo un paso de parámetros altamente eficiente hacia la red neuronal
- **Entrenamiento a Gran Escala con PPO**: Utilización del algoritmo Proximal Policy Optimization (PPO) mediante Gymnasium y Stable-Baselines3, acumulando más de 100 millones de pasos de entrenamiento (~1.12 días de cómputo continuo) con monitoreo de métricas mediante PyTorch y TensorFlow
- **Dashboard de Telemetría e Introspección de la IA**: Panel visual a tiempo real que desglosa el razonamiento del modelo: distribución de confianza por acción (logits), detección vectorial de peligros inmediatos (izquierda, frente, derecha) y distancia Manhattan relativa hacia la fruta
- **Pipeline de Conversión a ONNX**: Superación del reto de serialización y exportación del modelo desde el entorno de Python hacia el formato ONNX, asegurando un ejecutable ultraligero y de latencia imperceptible en la web
- **Modos de Juego Versátiles**: Modos Solo, Versus Humano vs IA y Modo Espectador, con soporte responsive y controles táctiles integrados para dispositivos móviles

### Logros Técnicos

- **100+ millones de pasos** de entrenamiento con algoritmo PPO
- **Inferencia en navegador** sin backend (ONNX Runtime Web)
- **Telemetría en tiempo real** del proceso de decisión de la IA
- **~1.12 días de cómputo** continuo para entrenamiento del modelo

### Problema Resuelto

Demostración práctica de Reinforcement Learning aplicado a videojuegos clásicos, con capacidad de inferencia 100% en el cliente y visualización del razonamiento de la IA en tiempo real.

---

## 4. Schools Landing & Admin Portal

**Estado:** 🚧 En Desarrollo (On Dev Stage)

### Stack Tecnológico
- Frontend: React, TypeScript/JavaScript, Tailwind CSS, HTML5, CSS3
- Backend & Servidores: Firebase (Authentication, Firestore Database)

### Descripción

Plataforma educativa integral que combina una interfaz pública (Landing Page) orientada a la atracción e información institucional con un robusto Portal de Administración multiusuario basado en roles. Permite centralizar la gestión académica, la asignación de tareas, el seguimiento de calificaciones y la comunicación institucional entre directivos, profesores, alumnos y tutores.

### Características Clave

#### Control de Acceso Basado en Roles (RBAC)
Arquitectura de permisos segmentada en 4 perfiles diferenciados:

1. **Directores/Administradores**: Gestión global de la planta docente, administración de matrículas y control operativo general
2. **Profesores**: Administración de cursos, asignación de tareas, publicación de recursos didácticos y evaluación de alumnos
3. **Alumnos**: Acceso a materiales educativos, entrega digital de asignaciones y consulta de calificaciones
4. **Padres/Tutores**: Supervisión continua del desempeño académico de sus hijos y recepción de boletines/comunicados

#### Tecnología

- **Backend Serverless con Firebase**: Implementación de Firebase Authentication para el manejo seguro de sesiones por rol y Firestore Database para la persistencia de datos relacionales/NoSQL en tiempo real (avisos, entregables y calificaciones)
- **Diseño Modular y Adaptable**: Desarrollo de componentes reactivos con React y Tailwind CSS, garantizando una experiencia de usuario fluida, responsiva y adaptable a la vista específica de cada usuario

### Problema Resuelto

Centralización de gestión académica institucional con control granular de permisos por rol, facilitando la comunicación entre todos los actores del ecosistema educativo (directivos, profesores, alumnos, padres).

---

## Resumen de Especialización

Estos 4 proyectos demuestran experiencia en:

✅ **Full-Stack Development**: Desde frontend vanilla hasta React/Next.js  
✅ **Arquitecturas Escalables**: REST APIs, arquitecturas desacopladas, Firebase  
✅ **Machine Learning & IA**: Reinforcement Learning, ONNX, inferencia en navegador  
✅ **RBAC & Seguridad**: Control de acceso basado en roles, autenticación segura  
✅ **Performance**: Optimización de carga, latencia imperceptible, SEO  
✅ **DevOps**: Despliegue en Netlify, Firebase, pipelines CI/CD