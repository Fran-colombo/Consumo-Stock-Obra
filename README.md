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

Completá en `.env` la clave JWT y el usuario administrador inicial. La clave del administrador tiene que tener al menos 8 caracteres. Si no hay usuarios y faltan esos datos, la API no arranca.

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

El primer ingreso usa el usuario definido en `CONKRETO_SYSADMIN_USER`. Ese usuario puede corregir o anular documentos ya confirmados. Los operadores registran operaciones nuevas y correcciones que dejan el movimiento original.

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
