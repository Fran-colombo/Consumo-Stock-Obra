# Conkreto

Aplicación interna para controlar materiales de obra: stock por ubicación, compras, transferencias y la comparación entre consumo teórico y real.

Los coeficientes los carga Conkreto para cada tarea. El sistema no trae recetas de construcción.

## Requisitos

- Python 3.12
- Node.js 22

## Configuración

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Completá en `.env` la clave JWT, el correo (`CONKRETO_SYSADMIN_EMAIL`) y la clave del administrador. La clave tiene que tener al menos 8 caracteres. Si no hay usuarios y faltan esos datos, la API no arranca.

```powershell
cd frontend
npm install
```

## Ejecución

En una terminal:

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

En otra:

```powershell
cd frontend
npx vite --host 127.0.0.1 --port 8087
```

Abrí `http://127.0.0.1:8087`. La base queda en `backend/data/conkreto.db` y se conserva al reiniciar.

El ingreso es el correo de `CONKRETO_SYSADMIN_EMAIL` y la clave de `CONKRETO_SYSADMIN_PASSWORD`. Ese usuario puede corregir o anular documentos ya confirmados. Los operadores registran operaciones nuevas y correcciones que dejan el movimiento original.

## Servidor

En el servidor no lo dejes en una terminal: al cerrar SSH se cae. Desde la raíz del repo, con `backend/.env` ya editado:

```bash
docker compose up -d --build
```

Queda publicado en el puerto 8087. `restart: unless-stopped` lo vuelve a levantar si se apaga el proceso o se reinicia la máquina. Cerrar la terminal no lo baja. Para ver si sigue arriba: `docker compose ps`. Para pararlo: `docker compose down`.

Si el administrador ya existía sin correo, el primer arranque de esta versión le asigna `CONKRETO_SYSADMIN_EMAIL` y toma la clave que esté en ese momento en `CONKRETO_SYSADMIN_PASSWORD`.

## Demostración

El script no se ejecuta al iniciar. El coeficiente que carga es solo un ejemplo de funcionamiento.

```powershell
cd backend
.\.venv\Scripts\python -m scripts.seed_demo
```

Si ya hay obras, se niega a continuar salvo que pases `--force`.

## Backup

Ver [docs/backup.md](docs/backup.md).

## Pruebas

```powershell
cd backend
.\.venv\Scripts\python -m pytest
```
