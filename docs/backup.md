# Backup y restauración

La base de la primera versión es el archivo SQLite `backend/data/conkreto.db`. Ahí están las obras, el libro de movimientos, los saldos y la auditoría.

## Copia

Con la API en marcha o detenida:

```powershell
cd backend
.\.venv\Scripts\python -m scripts.backup
```

El archivo queda en `backend/data/backups/`. La copia usa el backup de SQLite, así no se corta a la mitad si la aplicación está escribiendo.

También podés copiar `conkreto.db` con la API detenida.

## Restauración

1. Detené la API.
2. Ejecutá:

```powershell
cd backend
.\.venv\Scripts\python -m scripts.backup --restore data\backups\conkreto-FECHA.db
```

3. Volvé a iniciar la API.

La restauración reemplaza la base actual, incluida la auditoría. No hay un borrado de auditoría desde la aplicación: el registro de cambios se conserva en el archivo restaurado.
