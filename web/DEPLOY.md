# Deploy — GitHub → Vercel (público, sin auth)

> **Decisión informada:** el sitio queda **público** (sin login). Somos 2 personas y el riesgo está aceptado.
> Nada de esto está ejecutado. El push y el deploy los hacés vos siguiendo estos pasos.
> La web es 100% estática (HTML/CSS/JS + JSON). Vercel la sirve gratis.

---

## Estructura del repo (importante para Vercel)

El repo tiene la **app web en la subcarpeta `web/`** (no en la raíz):

```
OPEN LUB/                 ← raíz del repo
├── pipeline/             (Python: genera los JSON)
├── data/agg/             (resultados + dossiers; SÍ se versiona)
├── web/                  ← la app Vite vive acá
│   ├── src/
│   ├── public/data/      (players.json, teams.json — los sirve la web)
│   ├── package.json
│   └── ...
├── .gitignore           (excluye node_modules, dist, data/raw)
└── CLAUDE.md
```

Por eso en Vercel hay que fijar **Root Directory = `web`** (paso 3). Es el único detalle no obvio.

---

## 1. Crear el repo en GitHub y pushear

Desde la raíz del repo (`OPEN LUB/`), en una terminal:

```bash
git init
git add .
git commit -m "OpenLUB: pipeline de analítica + web interna Urunday"
```

Verificá que `node_modules/` NO entró (el `.gitignore` ya lo excluye):

```bash
git status --short        # no debería listar node_modules ni dist
```

Creá el repo remoto en GitHub:
- Opción A (web): <https://github.com/new> → nombre `openlub` (o el que quieras) → **Private o Public**
  (da igual para Vercel) → **Create repository**. Después:
  ```bash
  git branch -M main
  git remote add origin https://github.com/TU_USUARIO/openlub.git
  git push -u origin main
  ```
- Opción B (CLI `gh`): `gh repo create openlub --public --source=. --push`

---

## 2. Conectar Vercel al repo

1. Entrá a <https://vercel.com> y **Sign up / Log in con tu cuenta de GitHub** (gratis, plan Hobby).
2. **Add New… → Project**.
3. **Import Git Repository** → elegí el repo `openlub` que acabás de pushear.
   (La primera vez, Vercel te pide autorizar el acceso a tus repos de GitHub.)

---

## 3. Configurar el build (el paso clave por el subdirectorio)

En la pantalla de **Configure Project**:

| Campo | Valor |
|---|---|
| **Root Directory** | `web`  ← **cambialo a `web`** (botón *Edit* al lado de Root Directory) |
| **Framework Preset** | `Vite` (lo detecta solo al poner Root = web) |
| **Build Command** | `npm run build` (default de Vite, dejalo) |
| **Output Directory** | `dist` (default de Vite, dejalo) |
| **Install Command** | `npm install` (default) |

- No hace falta ninguna variable de entorno.
- **Deploy**. Vercel hace `npm install` + `npm run build` dentro de `web/` y publica `web/dist/`.

---

## 4. La URL pública

Al terminar (~1 min) Vercel te da la URL de producción:

```
https://<nombre-del-proyecto>.vercel.app
```

El `<nombre-del-proyecto>` es el que Vercel asigna al importar (por defecto, el nombre del repo;
podés cambiarlo en **Project → Settings → General → Project Name**). Esa es la URL que compartís
con el cuerpo técnico. Es pública: cualquiera con el link entra.

> Cada `git push` a `main` redeploya automáticamente. Para actualizar datos: re-correr el pipeline
> hasta `15_export_json` (regenera `web/public/data/*.json`) → `git commit` + `git push`. Vercel
> reconstruye solo. (No subas `dist/`: lo ignora el `.gitignore` y Vercel lo genera.)

---

## ✅ HashRouter funciona en Vercel SIN reescrituras

La web usa **HashRouter** a propósito. Las rutas son tipo `https://…vercel.app/#/team/CAP`:
el navegador **siempre pide `/`** al servidor (Vercel devuelve `index.html`) y el resto del path
(`#/team/CAP`) lo resuelve React en el cliente. El servidor nunca ve `/team/CAP`, así que **no hace
falta** ninguna regla de rewrite ni `vercel.json`. Por eso elegimos HashRouter: deploy estático directo,
recargar cualquier vista no da 404.

*(Si en el futuro se migra a `BrowserRouter` —URLs sin `#`— ahí sí haría falta un `vercel.json` con
un rewrite de todo a `/index.html`. Hoy NO se necesita.)*

---

### Costos
- Vercel plan **Hobby**: gratis para proyectos personales/estáticos. Sin tarjeta.
- Sin servidor, sin base de datos, sin auth.
