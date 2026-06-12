# CLAUDE.md — OpenACB para la LUB (estadística avanzada de básquet uruguayo)

## Objetivo
Replicar la funcionalidad analítica de OpenACB (https://github.com/juantorrecillas/openacb)
para la Liga Uruguaya de Básquetbol (LUB), usando los datos de FIBA LiveStats / Genius Sports
que publica la FUBB. Estadística avanzada: ratings, cuatro factores, on/off, quintetos,
cartas de tiro, gameflow, splits por cuarto, clutch.

## Alcance / Producto (DECIDIDO)
- **Web INTERNA del club** (estilo OpenACB), privada, **corre LOCAL**: sin hosting público, sin auth,
  sin backend vivo, sin base de datos. `npm run dev` o build estático.
- **Foco Urunday = de NAVEGACIÓN, no de datos.** El dataset es la **LIGA COMPLETA** (el Clasificatorio
  ya procesado): percentiles, scouting y comparaciones lo necesitan. CUALQUIER jugador de la liga
  (propio o rival) tiene su perfil — ver al anotador de Peñarol antes de jugarle es medio propósito.
  La web se organiza alrededor de Urunday (home = mi equipo) pero por dentro están TODOS.
- **Stack:** Vite + React que lee **JSON estático** generado por el pipeline (paso `15_export_json`).
  Sin servidor. Paleta de identidad: Urunday azul `#2563eb`, rival rojo `#dc2626`, fondo claro, Arial.
- Descartado: PDF de scouting (no era el objetivo). Los `.md` de scouting quedan como insumo interno.
- **DEPLOY (DECIDIDO): GitHub → Vercel, PÚBLICO sin auth.** Decisión informada: son 2 usuarios y el
  dueño aceptó el riesgo de dejarlo público (se descartó Cloudflare Access). Vercel plan Hobby gratis.
  Guía paso a paso en `web/DEPLOY.md`. Detalle clave: la app vive en `web/` → en Vercel **Root Directory
  = `web`**, build `npm run build`, output `dist`. HashRouter funciona sin reescrituras (por eso se eligió).
  El push y el deploy los hace el dueño; el repo ya tiene `.gitignore` (excluye node_modules, dist, data/raw).
- EXCLUIR aspectos económicos/financieros (no aplica a este proyecto).

## Fuente de datos (CONFIRMADO en sesión)
- Feed crudo FIBA LiveStats por partido:
  `https://fibalivestats.dcd.shared.geniussports.com/u/FUBB/{matchId}/` con vistas:
  `index.html` (resumen), `bs.html` (boxscore), `lds.html` (líderes),
  `pbp.html` (play-by-play), `sc.html` (carta de tiro), `st.html` (stats), `p.html` (previa).
- JSON crudo del partido (la fuente real a usar) — CONFIRMADO:
  `https://fibalivestats.dcd.shared.geniussports.com/data/{matchId}/data.json`
  Ej: `https://fibalivestats.dcd.shared.geniussports.com/data/2845330/data.json`
- El `data.json` ya fue inspeccionado: contiene TODO lo necesario (ver esquema abajo).

## IDs (CONFIRMADO)
- Competición LUB 25/26 = **42104** (en el embed de FUBB).
- El espacio de matchId es **único y compartido** entre el embed de FUBB y fibalivestats:
  el mismo número sirve en ambos sistemas. (Verificado: matchId 2845330 = Peñarol vs Urunday,
  carga idéntico en `fubb.org.uy/.../match/2845330/...` y en `fibalivestats.../u/FUBB/2845330/sc.html`.)
- Ejemplos: 2845330 = Peñarol-Urunday (LUB). 2849337 = Albatros-Marne (Liga de Ascenso, OTRA competición).
- Equipos (ejemplos): Peñarol = 96706, Urunday Universitario = 21051.

## Listado de partidos / Fases (CONFIRMADO — schedule = HTML, NO hay JSON)
DESCARTADO — el feed `data/competition/{id}.json` NO sirve para el schedule. Responde, pero
devuelve un único partido (el último/actual), array de objetos planos por partido SIN fase ni
lista completa. El `othermatches` del data.json de un partido viene vacío. No hay endpoint JSON
de schedule.

FUENTE REAL DEL SCHEDULE (CONFIRMADO, implementado en `pipeline/01_scrape.py`) — HTML
server-rendered del embed de FUBB, a parsear por fase:
`https://hosted.dcd.shared.geniussports.com/embednf/FUBB/es/competition/{competitionId}/schedule?phaseName={fase}`

La LUB 25/26 tiene CUATRO fases. Los `phaseName` van EXACTOS (con la errata):
1. `Clasificatorio LUB 25/26`     → 132 partidos (la "temporada regular", ver más abajo)
2. `Reclasificatiorio LUB 25/26`  →  17 partidos  (ERRATA "Reclasificatiorio" del sistema:
   si lo escribís bien, el endpoint devuelve 0 partidos)
3. `Titulo LUB 25/26`             →  30 partidos
4. `Playoffs LUB 25/26`           →  22 partidos
(Conteos al 2026-06-11. Total 201.)

GOTCHAS del parseo (NO obviar — costaron 0 resultados al primer intento):
- **Barras escapadas:** los links vienen como `...\/competition\/42104\/match\/2741411\/summary?...`
  dentro del HTML. El regex ingenuo `/match/(\d+)/` da 0. Usar: `match\\/(\d+)\\/summary`.
- **Duplicados:** cada partido aparece DOS veces (variantes `livenow` y `notlive` del mismo link).
  Hay que deduplicar (132 únicos de 264 ocurrencias en el Clasificatorio).

SALIDA del scraper: matchId ETIQUETADOS por fase (no lista plana) en
`data/schedule/schedule.json` (`{fase: [ids]}`) y `data/schedule/schedule.csv` (cols `matchId,fase`).
La fase es necesaria para tratar el Clasificatorio aparte del resto (ver "Decisión de diseño").

## Decisión de diseño sobre fases (DEFINIDA)
- **Clasificatorio = base.** Es la "temporada regular" real: muestra grande, oposición balanceada
  (todos contra todos). Usar SOLO esta fase para perfiles de jugador/equipo, percentiles vs liga,
  y similitud entre jugadores.
- Reclasificatorio / Título / Playoffs = **vistas separadas**, NUNCA agregadas al pool de
  Clasificatorio. Mezclarlas sesga las métricas (rivales más fuertes, muestras chicas, contexto
  de presión). Sí se pueden analizar por separado (p.ej. clutch/playoffs como módulo aparte).

## Esquema del `data.json` (lo relevante)
- `tm.{1,2}` : los dos equipos. Cada uno tiene:
  - `name`, `code`, `score`, `p1_score..p4_score`, `logoT.url`, totales `tot_s*`.
  - `pl.{playerId}` : jugadores, con boxscore individual, `playingPosition`, `shirtNumber`,
    `photoT`/`photoS` (URLs de foto), `starter`, `comp` (promedios de competición).
  - `shot[]` : tiros, A NIVEL EQUIPO (`tm.{1,2}.shot[]`, NO bajo cada jugador). Cada tiro trae
    `x`, `y` (0-100), `r` (1=encestado, 0=errado), `actionType` (2pt/3pt), `subType`
    (layup, jumpshot, pullupjumpshot, etc.), `p`/`pno`/`player` (jugador), `per` (período).
  - `scoring[]`, `lds` (líderes).
- NO hay campo `matchStatus` en el data.json (ese campo solo está en el endpoint de competición).
  El estado se DERIVA de `clock`/`period`/`periodsMax`/`periodType`/`score` (ver `pipeline/02_download.py`).
- GOTCHA prórroga: en OT el campo `period` REINICIA a 1 y `periodType` pasa a "OVERTIME"
  (no sigue 5,6...). Un partido finalizado en OT tiene `clock=00:00` con `periodType=OVERTIME`.
  Chequear solo `period >= periodsMax` da falso-incompleto en los partidos con prórroga.
- `pbp[]` : play-by-play completo, incluye `actionType="substitution"` (in/out) → ESTO permite
  reconstruir qué 5 jugadores hay en cancha en cada jugada (tracking de quintetos / on-off).
  Cada evento trae `s1`/`s2` (marcador), `tno` (equipo), `pno` (jugador), `gt` (game time), `per`.
- `leaddata` : evolución del marcador → gameflow.
- Logos, fotos y posiciones vienen embebidos → NO hace falta scrapear acb-style (pasos 10-12 de
  OpenACB se ahorran).

## Sistema de coordenadas de tiro (CRÍTICO — acá YA hubo un bug de ejes invertidos)
- `x`, `y` en escala 0-100 (porcentaje de cancha COMPLETA, 28m x 15m). `r`: 1=encestado, 0=errado
  (verificado cruzando contra `pbp` por `actionNumber`). Aro ≈ x:5 o x:95, y:50 (los layups caen ahí).
- Conversión a metros: `x_m = x*0.28`, `y_m = y*0.15`. Centrar en el aro (1.575m del fondo) para
  coords tipo FIBA (-7.3 a 7.3), como `05_shot_charts.R` de OpenACB.

- HAY DOS INVERSIONES INDEPENDIENTES. Confundirlas es lo que genera cartas espejadas. Mantenerlas
  SEPARADAS en el código, nunca acumularlas a ciegas:
  1. **Normalización de lado (analítica):** cada equipo cambia de aro por período (P1-P2 un lado,
     P3-P4 el otro). Para superponer en una media cancha, rotar 180° los tiros del lado lejano:
     `x' = 100-x`, `y' = 100-y`.
  2. **Convención de render (dibujo) — CONFIRMADO contra el oficial:** el feed guarda Y al revés
     de como se dibuja. Al PINTAR, X va DIRECTO e Y va INVERTIDO:
     - `cx = x/100 * ancho`   (X directo: x bajo = izquierda de pantalla)
     - `cy = (100 - y)/100 * alto`   (Y invertido: y alto = arriba de pantalla)
     Independiente de la normalización. Implementado en `pipeline/12_shotchart.py` (`render()`).
  - El bug "el tiro aparece en la banda equivocada" = invertir Y una vez de más/de menos al mezclar 1 y 2.
  - **HAY DOS RENDERS OFICIALES DE GENIUS ESPEJADOS EN Y** (verificado parseando ambos para Moller):
    - `fibalivestats .../u/FUBB/{id}/sc.html` → marcador en `bottom:y%; left:x%` (= `cy=100-y`). ESTE es
      la referencia del golden test y de `render()`. (Confirmado en su JS `ajload_2.js`.)
    - `hosted.dcd .../embednf/.../match/{id}/shotchart` → marcador en `top:y%; left:x%` → ESPEJADO en Y.
    NUNCA anclar la carta contra el embednf shotchart: reintroduce el bug de Y. Anclar SIEMPRE contra sc.html.
    (El embednf SÍ sirve para personId —paso 05—, pero NO como referencia de orientación de tiro.)

## TEST DE REGRESIÓN de orientación (golden test — debe pasar siempre)
Partido 2845330 (Peñarol-Urunday), A. Moller (#20), Período 1, sus 2 tiros de campo:
- 2pt pull-up ENCESTADO, feed `x≈7, y≈24`  → debe verse ABAJO-izquierda, pegado al aro.
- 3pt jumpshot FALLADO, feed `x≈23, y≈90`  → debe verse ARRIBA-izquierda, sobre el arco.
Verificado contra el render oficial de FIBA LiveStats. Si tu carta no reproduce esto (encestado
arriba o triple abajo), el eje Y está sin invertir o invertido de más. Este caso ancla el signo.

## REGLA DE ORO de orientación (OBLIGATORIA — NO validar cartas "a ojo")
La causa raíz del bug anterior fue validar la carta mirando si "se veía bien". Prohibido. Anclar
SIEMPRE contra ground truth antes de dar por buena cualquier carta:
1. Elegí un tiro identificable del `data.json` (jugador + cuarto + 2pt/3pt + subType).
2. Abrí el `sc.html` OFICIAL del MISMO partido (`fibalivestats.../u/FUBB/{matchId}/sc.html`). Ese
   render es la referencia correcta.
3. Verificá que ese tiro cae en la MISMA posición en tu carta y en el oficial.
   - Coinciden → orientación correcta, congelala.
   - No → sabés EXACTO qué eje flipear (X, Y o ambos). Corregí y re-anclá.
4. Repetí con un tiro de esquina (Y extremo) y uno bajo el aro (X extremo) para fijar AMBAS
   direcciones sin ambigüedad.
El anclaje contra el oficial elimina el bug; "se ve bien" lo reintroduce.

## Validación de calidad de datos (HACER ANTES de confiar en agregados)
- Medir dispersión de las coordenadas de layups a través de N partidos de Clasificatorio:
  deberían concentrarse en `x≈95±3` (o `5±3`) y `y≈50±8`. Si se concentran, el marcado es
  confiable a nivel liga. Si se dispersan, hay problema de operador y las cartas agregadas mienten.
- Validar el parseo: reconstruir el boxscore desde el `data.json` y compararlo contra el boxscore
  oficial del partido (debe coincidir exacto) ANTES de construir los 13 pasos encima.

## Política de exclusiones (incompletos genuinos)
- Un partido se considera COMPLETE si `clock=00:00` y (`period >= periodsMax` o `periodType=OVERTIME`)
  y su boxscore cierra (pts = score = suma de cuartos). Lo deriva `pipeline/02_download.py`.
- **Los incompletos genuinos** (suspendidos, feed congelado a mitad de partido, datos parciales)
  **SE EXCLUYEN del pool de agregados** (totales, promedios, líderes, percentiles, perfiles).
  NO se borran del cache crudo (`data/raw/matches/{matchId}.json` se conserva siempre).
- Toda exclusión se registra en `data/schedule/exclusions.csv` con `matchId, fase, motivo, fecha_excluido`.
  Los pasos analíticos leen ese log y descartan esos matchId antes de agregar.
- Caso registrado: `2741440` (Hebraica y Macabi vs Peñarol, Clasificatorio) suspendido en 2º cuarto
  (period=2, clock=00:43, solo 2 cuartos, 48-42). → 131/132 partidos válidos en el Clasificatorio.
- **Exclusión de LINEUP** (distinta): partidos con subs corruptos en el pbp que impiden reconstruir
  el quinteto, pero cuyo BOXSCORE es válido. Se excluyen SOLO del tracking de stints/on-off (siguen
  en los agregados de boxscore). Log: `data/schedule/lineup_exclusions.csv`. Caso: `2741514`
  (BIG vs UUN) — par `in#17/out#5` DUPLICADO + `in#11` redundante en P4 → quinteto cierra en 4.
- **Política con feed corrupto (REGLA):** si el feed está genuinamente corrupto (subs duplicados,
  invertidos o faltantes que no reconcilian), se EXCLUYE del on-court y se CONSERVA en el boxscore.
  NUNCA hand-patch por inferencia sobre el feed roto (inventaríamos quintetos). Hand-patch SOLO con
  fuente alternativa confiable (MyCourtFlow) que dé la secuencia real de cambios.

## On-court / tracking de stints (`pipeline/07_tracking.py`)
Reconstruye qué 5 hay en cancha por equipo desde las substitutions del pbp. GOTCHAS (todos resueltos):
- El **pbp viene en orden CRONOLÓGICO INVERSO** → iterar `reversed(pbp)`. Hay que procesar los subs
  simultáneos (cambios masivos de fin de cuarto) en orden cronológico REAL; reordenar por `clock`
  rompe el pareo in/out de esos instantes (era la causa de la mayoría de los quintetos != 5).
- **Tiempo:** usar el campo `clock` ("MM:SS:CC", centésimas), NO `gt` ("MM:SS") — `gt` pierde
  precisión y deja ±1s por jugador. Minutos del jugador = `round()` de los segundos (convención FIBA;
  floor/ceil dan ~0 exactos). Residual ±1-2s en ~40% de los partidos = ruido sub-segundo irreducible
  (reloj interno de FIBA vs centésimas del pbp); NO indica sub mal trackeado.
- **Quinteto inicial:** P1 = flag `starter` (da 5 exactos). P2+ = el quinteto PERSISTE del cierre
  anterior; los cambios de arranque vienen como subs en `clock=10:00` (0s antes) y lo ajustan.
- **OT:** `period` reinicia a 1 con `periodType=OVERTIME` → clave de período compuesta (OT período 1
  = período 5, largo 5:00). Sin esto la OT colisiona con el P1 regular.
- VALIDACIÓN (obligatoria antes de on/off): minutos del tracking == `sMinutes` por jugador y partido.
  Estado Clasificatorio: 130/130 trackeados OK (78 exactos al segundo + 52 dentro de ±1-2s, quinteto
  correcto), 0 mistracks; 1 excluido (2741514, feed corrupto).

## Identidad de jugador / equipo
- El `data.json` NO expone personId/teamId de jugador. Sus únicos `personId` son los de los 3
  ÁRBITROS (`officials.referee{1,2,3}.personId`). La clave `pl.{n}` y `pno`/`tno` son LOCALES al partido.
- **Equipo:** identidad estable = `code` (p.ej. "HYM", "CAP"); `name` para mostrar.
- **Jugador — CANÓNICO = `personId`** (global de Genius Sports; Moller = 1765563). NO está en el
  data.json: se cosecha del embed server-rendered (`pipeline/05_player_identity.py`):
  `https://hosted.dcd.shared.geniussports.com/embednf/FUBB/es/competition/{compId}/match/{matchId}/boxscore`
  Cada fila linkea a `/person/{personId}` con el nombre (en `alt` de la foto, o como texto del `<a>`).
  Se joinea al data.json por nombre normalizado, con fallback por apellido único en el partido.
  El crosswalk queda en `data/agg/{slug}/player_crosswalk.csv`.
  - OJO `sc_pn{personId}` del shotchart embednf se arma con `shot['p']`, que en el data.json archivado
    es el número LOCAL de roster — NO confundir con el personId global.
- Gotchas del harvest del embednf (todos resueltos en 05):
  - acentos/apóstrofes vienen como escapes unicode LITERALES (`Ñ` por Ñ) → desescapar antes de parsear.
  - normalizar nombre: sin acentos (NFKD), sin puntuación, mayúsculas, espacios colapsados.
  - algunos boxscores dan 404 transitorio → reintentar (no cachear el fallo).
- **NO usar** el hash de la URL de foto: INESTABLE (mismo jugador con varios hashes, ~70 sin foto).
- Por qué personId importa: la clave por nombre `(code, familyName, firstName)` PARTÍA al mismo jugador
  cuando el feed varía la grafía (MAYÚS vs Título, `Ñ`, Geronimo/Jeronimo, sufijo "Jr"). En el
  Clasificatorio: 8 jugadores así (colapsos), 0 falsos merges (splits=0). 228 claves-nombre → ~220
  personas reales. Su mayor valor aparece ENTRE fases (transferencias). Residual: ~3 jugadores con
  discrepancia de nombre fuente-a-fuente (apóstrofe, typo Glider/Gilder) en `identity_unmatched.csv`.

## Pipeline (adaptación de los 13 pasos de OpenACB, en Python)
Implementado: `01_scrape` (schedule), `02_download` (data.json + estado), `03_aggregate`
(boxscore agregado + líderes, **keyeado por personId** vía `player_id_map.csv` del paso 05),
`04_team_ratings` (ORtg/DRtg/pace/4 factores), `05_player_identity` (crosswalk personId),
`06_percentiles` (percentiles vs liga, pool MIN>=200), `07_tracking` (on-court/stints + validación
de minutos), `08_opportunity` (tasas USG/AST/REB/OREB/DREB/STL/BLK% on-court, integradas a percentiles),
`09_onoff` (on/off por jugador, net rating con él en cancha vs banca),
`10_lineups` (quintetos POR EQUIPO, net rating crudo, piso >=100 posesiones juntas),
`11_shotzones` (tiro por zona, sin render, validado vs boxscore), `12_shotchart` (carta visual SVG,
gateada por el golden test de Moller).
El paso 03 depende del 05: correr 05 antes (emite `player_id_map.csv` = matchId,team,name->personId).
Orden: 05 -> 03 -> 06 -> 07 -> 08 -> 09 -> 10 ; 11 y 12 (tiro) independientes.

### Cartas de tiro (pasos 11-12)
- `11_shotzones` (sin render): normaliza lado (fold 180°), clasifica zona (restringida/pintura/media;
  3 por sector esquina/ala/frente), FGA/FGM/eFG% por zona y equipo. VALIDA: eFG% por zonas == boxscore
  (los 12 equipos cuadran exacto → shot[] completo).
- `12_shotchart` (con render): aplica el flip de Y de dibujo (`cy=100-y`), SEPARADO del fold de lado.
  Antes de generar cartas corre el GOLDEN TEST de Moller; si no pasa, ABORTA. Genera SVG.
- `13_player_shotzones`: zonas + carta POR JUGADOR (personId, pool MIN>=200). FGA visible al lado de
  cada % (zonas de pocos intentos no son conclusión). Mismo gate de golden test. Genera scouting:
  cartas de los top-3 anotadores de cada rival. Salida `player_shotzones.csv` + `charts/players/`.
- `14_scouting`: dossier .md por rival (`scouting/{TEAM}.md`): (a) zona ATAQUE+DEFENSA vs liga,
  (b) generadores (PTS x USG% x AST% -> separa quién ARMA de quién solo anota), (c) ref a cartas.
  Etiqueta fuente: Clasificatorio (no playoffs ni imports tardíos). Defensa = lo que el rival le tira.
- `15_export_json`: exporta los CSV a JSON estático para la web (`web/public/data/players.json` keyed
  por personId = liga completa; `teams.json` con ratings+zonas atk/def+líderes+plantel) y copia las
  cartas a `web/public/charts/{personId}.svg`. `num()` PRESERVA decimales (percentiles 99.5 != 100).

## Web interna (`web/`, Vite + React, lee el JSON estático)
- Navegación HashRouter (sirve en static hosting sin reescrituras): `/` home (roster Urunday + buscador
  global de toda la liga), `/teams` (índice de los 12), `/player/:personId`, `/team/:code`.
- Componentes propios sin libs pesadas: `Radar.jsx` (percentil REAL, no redondeado) y `ShotChart.jsx`
  (carta de tiro DIBUJADA nativa: media cancha FIBA + puntos desde `shots` del JSON, convención de
  render `cy=100-y`, gateada por el golden test en el export). NO se usan SVGs pre-generados.
- **El perfil de EQUIPO incluye la LECTURA TÁCTICA de los dossiers** (no se queda en los .md):
  recuadro "Plan en 30s" (qué explotarles/quitarles/a quién presionar) + tabla de Generadores
  (cruce USG%×AST%, separa quién ARMA de quién anota). Se calcula en el paso 15 (`reading`, `generators`).
- Correr local: `cd web && npm run dev` (Vite `host:true`, puerto 5173). Datos: regenerar con paso 15. Las tasas de oportunidad usan denominadores ON-COURT (oportunidades
del equipo/rival mientras el jugador estuvo en cancha); validan que los 5 en cancha suman ~100% del usage.

### On/off (paso 09) — CRUDO, descriptivo, NO causal
- Mide si el equipo fue mejor/peor con el jugador EN CANCHA vs EN BANCA (ORtg/DRtg/Net on vs off,
  on_off = Net_on - Net_off). OFF = total del partido − ON, dentro de los partidos que jugó.
- **NO es causal:** no aísla el aporte del jugador de CON QUIÉN juega (un suplente que entra con
  titulares se infla; un titular sin descanso se deprime). No ajusta por compañeros/rivales. NO es RAPM.
- **Piso de muestra:** el diferencial es ruido si la muestra ON u OFF es chica (un iron-man tiene
  poquísimas posesiones en banca). Columna `qualified` = Poss_on y Poss_off >= 200. Sin el piso, el
  top se llena de iron-men de equipos malos (p.ej. Cordón con ~60 posesiones off). Reportar solo calificados.

### Quintetos (paso 10) — CRUDO, POR EQUIPO
- Net rating de cada quinteto (5 personId) con su ORtg/DRtg/Pos, agregado sobre los 130 partidos.
  Piso >=100 posesiones ofensivas juntas. Output `lineups_by_team.csv`, ordenado por equipo y posesiones.
- **Sin ajuste por rival -> NO COMPARABLE ENTRE EQUIPOS.** Un +15 de Cordón NO supera a un +10 de
  Peñarol (rivales distintos, muestra chica). Sirve solo DENTRO de un equipo.
- **CONCLUSIÓN (decidida):** en la LUB el quinteto NO es una unidad de análisis con muestra. Solo
  17 quintetos cruzan 100 posesiones en TODA la liga (máx 255; UUN tiene 1). El piso >=100 es correcto
  y deja ~1 por equipo A PROPÓSITO. No bajar el piso para "ver más" (sería ruido). Los equipos rotan
  demasiado (UUN usó 248 quintetos distintos) para que el lineup-de-5 sea base de perfiles/percentiles.
1. scrape: listar matchId por fase (parsear HTML de schedule) + bajar `data.json` por partido.
2. clean: eventos boxscore, contexto de tiro (transición, segunda oportunidad).
3. tracking: 5 en cancha por jugada (desde substitutions del pbp).
4. team_stats: ORtg, DRtg, cuatro factores (eFG%, TOV%, ORB%/DRB%, FT Rate).
5. shot_charts: normalizar coords (rotación 180°), distancia/ángulo al aro, clasificación en zonas.
6. lineup_analysis: individuales/parejas/tríos/quintetos, on/off, net rating.
7. player_stats: minutos, totales, percentiles vs liga (solo Clasificatorio), eficiencia.
8. game_flow: evolución del marcador (desde leaddata).
9. team_pace: splits por cuarto, ritmo.
10-12. logos/fotos/posiciones: extraer de los campos del data.json (no scrapear).
13. clutch_stats: últimos 5 min del 4º o prórroga con diferencia ≤ 5 (módulo aparte por fase).

## Stack
- **Python** (no R): `requests`, `pandas`, `beautifulsoup4` (parsear HTML de schedule), `json`.
- Sin navegador / Selenium: todo es HTTP + JSON + parseo de HTML estático.
- Frontend (opcional, si se hace público): React (como OpenACB). Hosting: Firebase (ya disponible)
  o Vercel.

## Consideraciones operativas
- Volumen: varios cientos de partidos si se cubren las 4 fases (+ Ascenso si se suma). Manejable.
- **Rate limiting**: poner delay entre requests (p.ej. 1-2s) para no ser bloqueado por Genius Sports.
- **Cachear** cada `data.json` crudo en disco (`data/raw/{matchId}.json`) antes de procesar.
  Reprocesar nunca debe rebajar todo de nuevo.
- Versionar con git desde el inicio.

## Orden de construcción recomendado (validación incremental)
1. Bajar y parsear UN solo partido (matchId 2845330) → reconstruir su boxscore → comparar con el oficial.
2. Recién con eso validado, escribir el scraper de schedule (las 4 fases) y bajar toda la temporada.
3. Recién con los datos crudos completos, construir los pasos analíticos 2-13.
NO pedir "scrapeá y analizá toda la LUB" de una: se construyen 13 pasos sobre un parseo sin validar.

## Pendiente de confirmar
- [x] Estructura del `42104.json`: RESUELTO — NO sirve para schedule (devuelve 1 partido, sin fase).
      Schedule = HTML por fase, implementado en `pipeline/01_scrape.py` (ver sección Listado/Fases).
- [x] `y` crudo de los 2 tiros de A. Moller (2845330): RESUELTO — 2pt pull-up encestado `x=6.55, y=24.01`;
      3pt fallado `x=22.78, y=90.40`. Golden test de ejes fijado al decimal (ver TEST DE REGRESIÓN).
      Nota: los `shot[]` viven a nivel EQUIPO (`tm.{1,2}.shot[]`), NO bajo cada jugador como decía el esquema.
- [ ] competitionId de la Liga de Ascenso (si se quiere incluir; es OTRA competición).
- [ ] Decisión de alcance: público liga-wide vs. herramienta de club.
