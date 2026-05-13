<img src="./images/logo.svg" alt="viviendascraper" height="56" />

Un buscador de viviendas en tiempo real que agrega resultados de múltiples portales inmobiliarios españoles con mapa interactivo integrado.

<img src="./images/header.jpg" alt="Vivienda Scraper Banner" height="336" />

![Vivienda Scraper](https://img.shields.io/badge/Python-3.13-blue?style=flat-square&logo=python)
![Angular](https://img.shields.io/badge/Angular-17-red?style=flat-square&logo=angular)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?style=flat-square&logo=fastapi)
![Leaflet](https://img.shields.io/badge/Leaflet-1.9-brightgreen?style=flat-square&logo=leaflet)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

## ✨ Características

- 🔍 **Búsqueda multi-plataforma**: Scraping automático de 6 portales inmobiliarios
  - [Idealista](https://www.idealista.com) ✅ (via undetected-chromedriver + sesión de usuario)
  - [Fotocasa](https://www.fotocasa.es) ✅
  - [Pisos.com](https://www.pisos.com) ✅
  - [Habitaclia](https://www.habitaclia.com) ✅
  - [YaEncontre](https://www.yaencontre.com) ✅
  - [Trovimap](https://www.trovimap.com) ✅

- 🗺️ **Mapa interactivo**: Visualiza propiedades en OpenStreetMap (sin API key)
  - Zoom automático a la ciudad buscada
  - Markers con información de cada propiedad
  - Integración con Nominatim para geocodificación

- 💾 **Caché inteligente**: Resultados cacheados durante 30 minutos
  - Acelera búsquedas repetidas
  - SQLite para almacenamiento persistente

- 🎨 **UI moderna**: Interfaz Angular 17 responsive con:
  - Filtros avanzados (precio, habitaciones, superficie)
  - Imágenes de propiedades
  - Badges de plataforma color-coded
  - Formularios reactivos

---

## 🚀 Instalación Rápida

### Requisitos previos

- **Python 3.13** (NO 3.14 — sin wheels para lxml y pydantic-core)
- **Node.js 18+** con npm
- **Git**

### 1. Clonar el repositorio

```bash
git clone https://github.com/yourusername/vivienda-scraper.git
cd vivienda-scraper
```

### 2. Arranque rápido (ambos servicios a la vez)

Si estás en Windows, puedes arrancar el backend y el frontend en dos ventanas separadas con un solo comando:

```powershell
.\start.ps1
```

O continúa con la configuración manual:

### 3. Configurar Backend manualmente (FastAPI)

```bash
cd backend

# Crear entorno virtual (opcional pero recomendado)
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Correr servidor en puerto 8000
py -3.13 -m uvicorn main:app --reload --port 8000
```

✅ Backend disponible en: `http://localhost:8000`

### 4. Configurar Frontend manualmente (Angular)

En otra terminal:

```bash
cd frontend

# Instalar dependencias
npm install

# Correr desarrollo en puerto 4200
ng serve
# O: npm start
```

✅ Frontend disponible en: `http://localhost:4200`

### 5. Usar la aplicación

1. Abre `http://localhost:4200` en tu navegador
2. Selecciona una ciudad (ej: "Madrid", "Barcelona", "Almería")
3. Ajusta filtros de precio, habitaciones, superficie
4. Selecciona plataformas (todos activados por defecto)
5. Haz clic en "Buscar viviendas"
6. Explora resultados + mapa interactivo

---

## 🔑 API Keys Opcionales

### Idealista (requiere API key — DataDome bloquea scraping directo)

Idealista usa DataDome como sistema anti-bot, que no puede bypasearse con scrapers HTTP ni Playwright. La única vía es la API oficial. Para habilitarlo:

1. **Registrate en Idealista API**: [https://api.idealista.com/commercials](https://api.idealista.com/commercials)

2. **Obtén tus credenciales**: API key e API secret

3. **Configura en backend** (`backend/scrapers/idealista_scraper.py`):
   ```python
   # Reemplaza con tus credenciales
   API_KEY = "tu_api_key_aqui"
   API_SECRET = "tu_api_secret_aqui"
   ```

4. **Reinicia el backend**:
   ```bash
   py -3.13 -m uvicorn main:app --reload --port 8000
   ```

### OpenStreetMap / Nominatim (Incluido - Sin API key)

El mapa usa Nominatim (OpenStreetMap) para geocodificación. **No requiere API key**. Límite: 1 req/seg (respetado por la app).

---

## 📁 Estructura del Proyecto

```
vivienda-scraper/
├── backend/
│   ├── main.py                      # Aplicación FastAPI
│   ├── requirements.txt             # Dependencias Python
│   ├── api/
│   │   └── routes.py               # Endpoints REST
│   ├── models/
│   │   └── property.py             # Modelos Pydantic
│   ├── scrapers/
│   │   ├── base_scraper.py         # Clase base
│   │   ├── pisos_scraper.py        # ✅ Scraper Pisos.com
│   │   ├── fotocasa_scraper.py     # ✅ Scraper Fotocasa
│   │   ├── habitaclia_scraper.py   # ✅ Scraper Habitaclia
│   │   ├── yaencontre_scraper.py   # ✅ Scraper YaEncontre
│   │   ├── trovimap_scraper.py     # ✅ Scraper Trovimap
│   │   └── idealista_scraper.py    # ❌ Requiere API key
│   ├── services/
│   │   ├── search_service.py       # Orquestación de scrapers
│   │   └── cache_service.py        # Caché SQLite
│   └── config/
│       └── settings.py             # Configuración global
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── app.component.ts    # Componente raíz + lógica
│   │   │   ├── app.component.html  # Template con mapa + resultados
│   │   │   ├── app.component.scss  # Estilos (diseño responsive)
│   │   │   ├── models/
│   │   │   │   └── property.model.ts
│   │   │   └── services/
│   │   │       └── search-api.service.ts
│   │   ├── styles.scss
│   │   └── index.html
│   ├── angular.json
│   ├── package.json
│   └── tsconfig.json
│
└── README.md                        # Este archivo
```

---

## 🔌 Endpoints API Backend

### `GET /health`
Verificar estado del servidor.

```bash
curl http://localhost:8000/health
```

### `GET /api/platforms`
Obtener lista de plataformas disponibles.

```bash
curl http://localhost:8000/api/platforms
```

Respuesta:
```json
[
  {"key": "fotocasa", "name": "Fotocasa", "available": true},
  {"key": "pisos", "name": "Pisos", "available": true},
  ...
]
```

### `GET /api/search`
Buscar propiedades con filtros.

**Parámetros query:**
- `city` (string): Ciudad a buscar. Ej: "madrid", "barcelona", "almeria"
- `price_min` (int, opcional): Precio mínimo en €
- `price_max` (int, opcional): Precio máximo en €
- `rooms_min` (int, opcional): Habitaciones mínimas
- `size_min` (int, opcional): Superficie mínima en m²
- `size_max` (int, opcional): Superficie máxima en m²
- `platforms` (array, opcional): Plataformas a incluir. Ej: `?platforms=pisos&platforms=fotocasa`
- `page` (int, opcional): Página de resultados (default: 1)

**Ejemplo:**
```bash
curl "http://localhost:8000/api/search?city=almeria&price_max=200000&platforms=pisos&platforms=fotocasa"
```

**Respuesta:**
```json
{
  "total": 13,
  "page": 1,
  "results": [
    {
      "id": "...",
      "title": "Piso en calle...",
      "price": 125000,
      "price_per_m2": 912.5,
      "size_m2": 137,
      "rooms": 3,
      "bathrooms": 2,
      "address": "calle Quevedo, 2",
      "city": "almeria",
      "platform": "pisos",
      "images": ["https://..."],
      "url": "https://www.pisos.com/comprar/...",
      "scraped_at": "2026-05-12T10:30:00Z"
    },
    ...
  ],
  "platforms_queried": ["pisos", "fotocasa"]
}
```

### ⚠️ Limitaciones Conocidas

#### Filtrado por Barrio/Zona (Parámetro `district`) - ✅ IMPLEMENTADO

**Cómo funciona:**
- El campo `district` ahora **sí funciona** con búsqueda en tiempo real
- Cuando ingresas un barrio (ej: "Retamar", "Toyo"), el sistema busca ese término en:
  - Título de la propiedad
  - Dirección/Ubicación
  - Descripción (si está disponible)

**Nota importante:**
- Los portales inmobiliarios **NO soportan filtrado por barrio en sus URLs**
- Por eso usamos búsqueda post-scraping: obtenemos todos los resultados de la ciudad y filtramos localmente por barrio
- Esto funciona mejor si el barrio está explícitamente mencionado en la dirección

**Ejemplo:**
- Búsqueda: Ciudad "Almería" + Barrio "Retamar"
- Resultado: Todas las propiedades de Almería que mencionen "Retamar" en su información

---

## 🛠️ Desarrollo

### Stack Tecnológico

**Backend:**
- FastAPI 0.115.5 — Framework web asincrónico
- Python 3.13 — Lenguaje
- cloudscraper — Anti-bot bypassing
- BeautifulSoup4 + lxml — Parsing HTML
- SQLAlchemy — ORM para caché
- Pydantic v2 — Validación de datos

**Frontend:**
- Angular 17 — Framework UI
- TypeScript 5.4 — Tipado fuerte
- Reactive Forms — Formularios complejos
- Leaflet 1.9.4 — Mapas interactivos
- SCSS — Pre-procesamiento CSS

### Caché

Las búsquedas se cacheán en `backend/cache.db` durante **30 minutos**. Para limpiar:

```bash
cd backend
# Windows:
Remove-Item cache.db -Force

# Linux/Mac:
rm cache.db
```

### Logs

El backend muestra logs en consola:
```
INFO:     Application startup complete
DEBUG:    Searching platform: pisos...
DEBUG:    Found 5 properties from pisos
```

---

## ⚠️ Limitaciones Conocidas

| Plataforma | Estado | Notas |
|-----------|--------|-------|
| **Fotocasa** | ✅ Funcional | JS-lazy loaded, ~1-5 props/página |
| **Pisos.com** | ✅ Funcional | Buena cobertura, 10-15 props/página |
| **Habitaclia** | ✅ Funcional | Cobertura media |
| **YaEncontre** | ✅ Funcional | Cobertura media |
| **Trovimap** | ✅ Funcional | Cobertura media |
| **Idealista** | ✅ Funcional | Via undetected-chromedriver + sesión guardada (`save_idealista_cookies.py`) |

**Coordinadas GPS:** La mayoría de scrapers no extraen `lat/lon`. El mapa usa Nominatim para centrar en la ciudad buscada.

---

## 🤝 Contribuyendo

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Haz commit: `git commit -am 'Añade nueva funcionalidad'`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Pull Request

---

## 📝 Licencia

Distribuido bajo licencia MIT. Ver `LICENSE` para más detalles.

---

## 👤 Autor

**Tu nombre** — [GitHub](https://github.com/yourusername) | [LinkedIn](https://linkedin.com/in/yourprofile)

---

## 📞 Soporte

- 🐛 **Issues**: [GitHub Issues](https://github.com/yourusername/vivienda-scraper/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/yourusername/vivienda-scraper/discussions)
- 📧 **Email**: tu.email@ejemplo.com

---

## 🎯 Roadmap

- [ ] Agregar más portales (Fotopropiedad, Europapress, etc.)
- [ ] Exportar resultados a CSV/JSON
- [ ] Filtros avanzados por tipo de inmueble
- [ ] Alertas por email de nuevas propiedades
- [ ] Historial de búsquedas
- [ ] Comparador de propiedades
- [ ] App móvil (React Native)

---

**Última actualización**: 12 de mayo de 2026

⭐ Si te resultó útil, considera dejar una estrella en GitHub!
