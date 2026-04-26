"""
Module partagé : calcul des coûts et génération du rapport HTML.
"""

import re
import json
import email.header
from datetime import datetime
from collections import defaultdict

# ── Coûts annexes (ajustez selon votre situation) ─────────────────────────────

DISTANCE_KM   = 13.5    # km one-way : Lessard-et-le-Chêne → Gare de Lisieux (OSRM)
RATE_KM       = 0.548   # €/km — barème kilométrique 2025, véhicule 5 CV, tranche < 5 000 km/an
METRO_TICKET  = 2.50    # €/trajet — zones 1-3, ligne 13 Saint-Lazare ↔ Saint-Denis Université (2025)
LUNCH_COST    = 15.00   # € — repas du midi (à ajuster)

# ── Helpers communs ───────────────────────────────────────────────────────────

def decode_header_str(raw):
    parts = email.header.decode_header(raw or "")
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="replace")
        else:
            result += part
    return result

def extract_amount(text):
    match = re.search(r'Total commande\s*:\s*([\d \xa0,]+)\s*\S*€', text)
    if match:
        raw = re.sub(r'[\s\xa0]', '', match.group(1)).replace(',', '.')
        try:
            return float(raw)
        except ValueError:
            pass
    return None

def parse_subject(subject):
    route = travel_date = return_date = ""
    m = re.search(r'Votre voyage (.+?),\s*aller', subject)
    if m: route = m.group(1).strip()
    m = re.search(r'aller le (.+?)(?:,\s*retour|$)', subject)
    if m: travel_date = m.group(1).strip()
    m = re.search(r'retour le (.+?)(?:\s*-|$)', subject)
    if m: return_date = m.group(1).strip()
    return route, travel_date, return_date

# ── Calcul des coûts annexes ──────────────────────────────────────────────────

def compute_extra(trip):
    """
    Retourne (car, metro, lunch) pour un trajet.

    Logique :
    - Voiture  : aller-retour si le mail contient un retour, sinon aller simple.
    - Métro    : idem (ligne 13, zones 1-3).
    - Repas    : uniquement les jours de départ vers Paris (Lisieux → Paris).
    """
    to_paris  = trip["route"].lower().startswith("lisieux")
    n_legs    = 2 if trip.get("return_date") else 1

    car   = round(DISTANCE_KM * n_legs * RATE_KM, 2)
    metro = round(METRO_TICKET * n_legs, 2)
    lunch = LUNCH_COST if to_paris else 0.0

    return car, metro, lunch

# ── Génération HTML ───────────────────────────────────────────────────────────

def generate_html(trips, report_file):
    # Enrichir chaque trajet avec les coûts annexes
    for t in trips:
        car, metro, lunch = compute_extra(t)
        t["car"]       = car
        t["metro"]     = metro
        t["lunch"]     = lunch
        t["extra"]     = round(car + metro + lunch, 2)
        amt            = t["amount"] or 0
        t["full"]      = round(amt + car + metro + lunch, 2)

    # ── Statistiques globales ────────────────────────────────────────────────
    total_train  = sum(t["amount"] or 0  for t in trips)
    total_car    = sum(t["car"]          for t in trips)
    total_metro  = sum(t["metro"]        for t in trips)
    total_lunch  = sum(t["lunch"]        for t in trips)
    total_all    = sum(t["full"]         for t in trips)

    # Cumuls par année / mois (sur coût total)
    by_year  = defaultdict(float); by_year_cnt  = defaultdict(int)
    by_month = defaultdict(float); by_month_cnt = defaultdict(int)
    for t in trips:
        if t["year"]:
            by_year[t["year"]]  += t["full"]; by_year_cnt[t["year"]]  += 1
        if t["month"]:
            by_month[t["month"]] += t["full"]; by_month_cnt[t["month"]] += 1

    # ── Rows avec cumuls progressifs ─────────────────────────────────────────
    rows = []
    c_total = c_year = c_month = 0.0
    prev_y = prev_m = ""
    for i, t in enumerate(trips):
        if t["year"]  != prev_y: c_year  = 0.0; prev_y = t["year"]
        if t["month"] != prev_m: c_month = 0.0; prev_m = t["month"]
        c_total += t["full"]; c_year += t["full"]; c_month += t["full"]
        rows.append({
            "num":           i + 1,
            "purchase_date": t["purchase_date"],
            "year":          t["year"],
            "month":         t["month"],
            "route":         t["route"],
            "travel_date":   t["travel_date"],
            "return_date":   t["return_date"],
            "train":  f'{t["amount"] or 0:.2f}',
            "car":    f'{t["car"]:.2f}',
            "metro":  f'{t["metro"]:.2f}',
            "lunch":  f'{t["lunch"]:.2f}',
            "extra":  f'{t["extra"]:.2f}',
            "full":   f'{t["full"]:.2f}',
            "c_month": f'{c_month:.2f}',
            "c_year":  f'{c_year:.2f}',
            "c_total": f'{c_total:.2f}',
        })

    year_data  = [{"year": y,  "total": round(by_year[y], 2),  "count": by_year_cnt[y]}
                  for y in sorted(by_year)]
    month_data = [{"month": m, "total": round(by_month[m], 2), "count": by_month_cnt[m]}
                  for m in sorted(by_month)]

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Billets SNCF — Analyse des dépenses</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f4f4;color:#333}}
header{{background:#c62828;color:#fff;padding:22px 32px}}
header h1{{font-size:1.5rem;font-weight:700}}
header p{{opacity:.75;margin-top:4px;font-size:.85rem}}
.section{{padding:20px 32px}}
.section>h2{{font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#999;margin-bottom:14px}}
/* Cards */
.cards{{display:flex;gap:12px;flex-wrap:wrap}}
.card{{background:#fff;border-radius:8px;padding:16px 20px;flex:1;min-width:120px;box-shadow:0 1px 3px rgba(0,0,0,.09)}}
.card .lbl{{font-size:.7rem;color:#999;text-transform:uppercase;letter-spacing:.05em}}
.card .val{{font-size:1.5rem;font-weight:700;margin-top:3px}}
.card.train .val{{color:#c62828}}
.card.car   .val{{color:#1565c0}}
.card.metro .val{{color:#6a1b9a}}
.card.lunch .val{{color:#e65100}}
.card.total .val{{color:#2e7d32}}
/* Config bar */
.config-bar{{background:#fff;border-radius:8px;padding:14px 20px;box-shadow:0 1px 3px rgba(0,0,0,.09);display:flex;gap:20px;flex-wrap:wrap;align-items:center}}
.config-bar label{{font-size:.82rem;color:#555;display:flex;flex-direction:column;gap:3px}}
.config-bar input{{padding:5px 8px;border:1px solid #ddd;border-radius:5px;font-size:.85rem;width:100px}}
.config-bar button{{padding:7px 16px;background:#c62828;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.85rem;font-weight:600;align-self:flex-end}}
.config-bar button:hover{{background:#b71c1c}}
/* Charts */
.chart-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:680px){{.chart-grid{{grid-template-columns:1fr}}}}
.chart-box{{background:#fff;border-radius:8px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.09)}}
.chart-box h3{{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#bbb;margin-bottom:12px}}
.tabs{{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:12px}}
.tab{{padding:4px 13px;border-radius:20px;border:2px solid #ddd;background:#fff;cursor:pointer;font-size:.8rem;font-weight:600;color:#666;transition:all .12s}}
.tab.active{{background:#c62828;border-color:#c62828;color:#fff}}
.bar-row{{display:flex;align-items:center;margin-bottom:7px;gap:9px}}
.bar-lbl{{width:80px;font-size:.73rem;color:#555;flex-shrink:0;text-align:right}}
.bar-wrap{{flex:1;background:#f0f0f0;border-radius:4px;height:19px;overflow:hidden}}
.bar{{height:100%;border-radius:4px;display:flex;align-items:center;padding-left:6px;min-width:2px}}
.bar.red{{background:#c62828}} .bar.blue{{background:#1565c0}}
.bar span{{font-size:.68rem;color:#fff;font-weight:600;white-space:nowrap}}
/* Controls */
.controls{{display:flex;gap:9px;flex-wrap:wrap;align-items:center;padding:0 32px 10px}}
.controls input,.controls select{{padding:6px 10px;border:1px solid #ddd;border-radius:6px;font-size:.84rem;background:#fff}}
.controls input{{width:190px}}
/* Table */
.table-wrap{{padding:0 32px 48px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.09);font-size:.81rem}}
thead tr{{background:#c62828;color:#fff}}
th{{padding:9px 11px;text-align:left;font-weight:600;cursor:pointer;user-select:none;white-space:nowrap}}
th:hover{{background:#b71c1c}}
th.sorted-asc::after{{content:' ↑'}} th.sorted-desc::after{{content:' ↓'}}
tbody tr{{border-bottom:1px solid #f0f0f0}} tbody tr:hover{{background:#fafafa}}
td{{padding:7px 11px;white-space:nowrap}}
td.num{{color:#ccc;width:34px}}
td.r{{text-align:right;font-weight:600}}
td.train{{color:#c62828}}
td.car{{color:#1565c0}}
td.metro{{color:#6a1b9a}}
td.lunch{{color:#e65100}}
td.full{{color:#333;background:#f9f9f9}}
td.cm{{color:#1565c0}} td.cy{{color:#6a1b9a}} td.ct{{color:#2e7d32;font-weight:700}}
tfoot tr{{background:#fff3f3;border-top:2px solid #c62828}}
tfoot td{{padding:9px 11px;font-weight:700}}
.empty{{text-align:center;padding:36px;color:#bbb;font-style:italic}}
</style>
</head>
<body>
<header>
  <h1>Billets SNCF Connect — Analyse des dépenses</h1>
  <p>Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} · {len(trips)} billets</p>
</header>

<!-- Résumé par poste de dépense -->
<div class="section">
  <h2>Résumé global</h2>
  <div class="cards">
    <div class="card train"><div class="lbl">Train (SNCF)</div><div class="val" id="s-train">{total_train:.2f} €</div></div>
    <div class="card car">  <div class="lbl">Voiture ({DISTANCE_KM} km × {RATE_KM} €)</div><div class="val" id="s-car">{total_car:.2f} €</div></div>
    <div class="card metro"><div class="lbl">Métro ({METRO_TICKET} €/trajet)</div><div class="val" id="s-metro">{total_metro:.2f} €</div></div>
    <div class="card lunch"><div class="lbl">Repas midi ({LUNCH_COST} €)</div><div class="val" id="s-lunch">{total_lunch:.2f} €</div></div>
    <div class="card total"><div class="lbl">Total tous frais</div><div class="val" id="s-total">{total_all:.2f} €</div></div>
    <div class="card"      ><div class="lbl">Moyenne / billet</div><div class="val" id="s-avg">{total_all/len(trips):.2f} €</div></div>
  </div>
</div>

<!-- Paramètres ajustables -->
<div class="section">
  <h2>Paramètres</h2>
  <div class="config-bar">
    <label>Distance (km aller)<input type="number" id="p-dist"  step="0.5" value="{DISTANCE_KM}"></label>
    <label>Taux kilométrique (€/km)<input type="number" id="p-rate"  step="0.001" value="{RATE_KM}"></label>
    <label>Ticket métro (€/trajet)<input type="number" id="p-metro" step="0.05"  value="{METRO_TICKET}"></label>
    <label>Repas midi (€)<input type="number" id="p-lunch" step="0.50"  value="{LUNCH_COST}"></label>
    <button onclick="recalculate()">Recalculer</button>
  </div>
</div>

<!-- Graphiques par période -->
<div class="section">
  <h2>Dépenses par période (coût total)</h2>
  <div class="chart-grid">
    <div class="chart-box"><h3>Par année</h3><div id="chart-year"></div></div>
    <div class="chart-box">
      <h3>Par mois</h3>
      <div class="tabs" id="year-tabs"></div>
      <div id="chart-month"></div>
    </div>
  </div>
</div>

<!-- Tableau -->
<div class="controls">
  <input type="text" id="search" placeholder="Rechercher…">
  <select id="f-year"><option value="">Toutes les années</option></select>
  <select id="f-month"><option value="">Tous les mois</option></select>
  <select id="sort-field">
    <option value="purchase_date">Date achat</option>
    <option value="train">Train</option>
    <option value="full">Total jour</option>
    <option value="route">Trajet</option>
  </select>
  <select id="sort-dir">
    <option value="asc">↑ Croissant</option>
    <option value="desc">↓ Décroissant</option>
  </select>
</div>

<div class="table-wrap">
  <table>
    <thead><tr>
      <th class="num" data-col="num">#</th>
      <th data-col="purchase_date">Date achat</th>
      <th data-col="route">Trajet</th>
      <th data-col="travel_date">Voyage</th>
      <th data-col="return_date">Retour</th>
      <th data-col="train"  style="text-align:right">Train</th>
      <th data-col="car"    style="text-align:right">Voiture</th>
      <th data-col="metro"  style="text-align:right">Métro</th>
      <th data-col="lunch"  style="text-align:right">Repas</th>
      <th data-col="full"   style="text-align:right">Total jour</th>
      <th style="text-align:right">∑ mois</th>
      <th style="text-align:right">∑ année</th>
      <th style="text-align:right">∑ total</th>
    </tr></thead>
    <tbody id="tbody"></tbody>
    <tfoot id="tfoot"></tfoot>
  </table>
</div>

<script>
// ── Données ───────────────────────────────────────────────────────────────────
let BASE_ROWS = {json.dumps(rows, ensure_ascii=False)};
let YEAR_DATA  = {json.dumps(year_data,  ensure_ascii=False)};
let MONTH_DATA = {json.dumps(month_data, ensure_ascii=False)};

let sortCol='purchase_date', sortDir='asc', search='', fYear='', fMonth='';
const fmt = v => parseFloat(v).toLocaleString('fr-FR', {{minimumFractionDigits:2,maximumFractionDigits:2}});

// ── Recalcul côté client ──────────────────────────────────────────────────────
function recalculate() {{
  const dist  = parseFloat(document.getElementById('p-dist').value)  || {DISTANCE_KM};
  const rate  = parseFloat(document.getElementById('p-rate').value)  || {RATE_KM};
  const metro = parseFloat(document.getElementById('p-metro').value) || {METRO_TICKET};
  const lunch = parseFloat(document.getElementById('p-lunch').value) || {LUNCH_COST};

  // Reconstruire les rows depuis les données brutes d'origine
  BASE_ROWS = {json.dumps(rows, ensure_ascii=False)}.map(r => {{
    const nLegs    = r.return_date ? 2 : 1;
    const toParis  = r.route.toLowerCase().startsWith('lisieux');
    const car_v    = Math.round(dist * nLegs * rate   * 100) / 100;
    const metro_v  = Math.round(metro * nLegs          * 100) / 100;
    const lunch_v  = toParis ? lunch : 0;
    const extra_v  = Math.round((car_v + metro_v + lunch_v) * 100) / 100;
    const train_v  = parseFloat(r.train) || 0;
    const full_v   = Math.round((train_v + extra_v) * 100) / 100;
    return {{ ...r, car: car_v.toFixed(2), metro: metro_v.toFixed(2),
              lunch: lunch_v.toFixed(2), extra: extra_v.toFixed(2),
              full: full_v.toFixed(2) }};
  }});

  // Recalculer cumuls par mois / année
  const byM = {{}}, byY = {{}}, byMc = {{}}, byYc = {{}};
  BASE_ROWS.forEach(r => {{
    const v = parseFloat(r.full)||0;
    if(r.month){{ byM[r.month]=(byM[r.month]||0)+v; byMc[r.month]=(byMc[r.month]||0)+1; }}
    if(r.year) {{ byY[r.year] =(byY[r.year] ||0)+v; byYc[r.year] =(byYc[r.year] ||0)+1; }}
  }});
  YEAR_DATA  = Object.keys(byY).sort().map(y=>  ({{year:y,  total:Math.round(byY[y]*100)/100,  count:byYc[y]}}));
  MONTH_DATA = Object.keys(byM).sort().map(m=>  ({{month:m, total:Math.round(byM[m]*100)/100, count:byMc[m]}}));

  renderYearChart(); renderMonthChart(activeYear); updateSummary(); render();
}}

function updateSummary() {{
  const tTrain  = BASE_ROWS.reduce((s,r)=>s+(parseFloat(r.train)||0),  0);
  const tCar    = BASE_ROWS.reduce((s,r)=>s+(parseFloat(r.car)||0),    0);
  const tMetro  = BASE_ROWS.reduce((s,r)=>s+(parseFloat(r.metro)||0),  0);
  const tLunch  = BASE_ROWS.reduce((s,r)=>s+(parseFloat(r.lunch)||0),  0);
  const tAll    = BASE_ROWS.reduce((s,r)=>s+(parseFloat(r.full)||0),   0);
  document.getElementById('s-train').textContent = fmt(tTrain)  + ' €';
  document.getElementById('s-car').textContent   = fmt(tCar)    + ' €';
  document.getElementById('s-metro').textContent = fmt(tMetro)  + ' €';
  document.getElementById('s-lunch').textContent = fmt(tLunch)  + ' €';
  document.getElementById('s-total').textContent = fmt(tAll)    + ' €';
  document.getElementById('s-avg').textContent   = fmt(tAll / BASE_ROWS.length) + ' €';
}}

// ── Charts ────────────────────────────────────────────────────────────────────
function renderYearChart() {{
  const max = Math.max(...YEAR_DATA.map(d=>d.total));
  document.getElementById('chart-year').innerHTML = YEAR_DATA.map(d =>
    `<div class="bar-row"><div class="bar-lbl">${{d.year}}</div>
     <div class="bar-wrap"><div class="bar blue" style="width:${{(d.total/max*100).toFixed(1)}}%">
     <span>${{fmt(d.total)}} € (${{d.count}})</span></div></div></div>`
  ).join('');
}}

let activeYear = 'all';
function renderMonthChart(year) {{
  const data = year==='all' ? MONTH_DATA : MONTH_DATA.filter(d=>d.month.startsWith(year));
  if (!data.length) {{ document.getElementById('chart-month').innerHTML='<p style="color:#ccc;font-size:.82rem;padding:8px">Aucune donnée</p>'; return; }}
  const max = Math.max(...data.map(d=>d.total));
  document.getElementById('chart-month').innerHTML = data.map(d => {{
    const [y,m] = d.month.split('-');
    const lbl = new Date(y,m-1,1).toLocaleDateString('fr-FR',{{month:'short',year:'2-digit'}});
    return `<div class="bar-row"><div class="bar-lbl">${{lbl}}</div>
     <div class="bar-wrap"><div class="bar red" style="width:${{(d.total/max*100).toFixed(1)}}%">
     <span>${{fmt(d.total)}} €</span></div></div></div>`;
  }}).join('');
}}

function buildTabs() {{
  const tabs = document.getElementById('year-tabs');
  tabs.innerHTML = ['all',...YEAR_DATA.map(d=>d.year)].map(y =>
    `<button class="tab ${{y==='all'?'active':''}}" data-y="${{y}}">${{y==='all'?'Toutes':y}}</button>`
  ).join('');
  tabs.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {{
    activeYear = b.dataset.y;
    tabs.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t===b));
    renderMonthChart(activeYear);
  }}));
}}

// ── Filtres ───────────────────────────────────────────────────────────────────
function buildFilters() {{
  const sy = document.getElementById('f-year');
  const sm = document.getElementById('f-month');
  [...new Set(BASE_ROWS.map(r=>r.year).filter(Boolean))].sort().forEach(y => {{
    const o=document.createElement('option'); o.value=y; o.textContent=y; sy.appendChild(o);
  }});
  [...new Set(BASE_ROWS.map(r=>r.month).filter(Boolean))].sort().forEach(m => {{
    const [y,mo]=m.split('-');
    const lbl=new Date(y,mo-1,1).toLocaleDateString('fr-FR',{{month:'long',year:'numeric'}});
    const o=document.createElement('option'); o.value=m; o.textContent=lbl; sm.appendChild(o);
  }});
}}

// ── Table ─────────────────────────────────────────────────────────────────────
function render() {{
  let rows = BASE_ROWS.filter(r => {{
    if (fYear  && r.year  !== fYear)  return false;
    if (fMonth && r.month !== fMonth) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return r.route.toLowerCase().includes(q) || r.purchase_date.includes(q) ||
           r.travel_date.toLowerCase().includes(q);
  }});
  rows = rows.slice().sort((a,b) => {{
    let va=a[sortCol], vb=b[sortCol];
    if (['train','car','metro','lunch','full','num'].includes(sortCol)) {{ va=parseFloat(va)||0; vb=parseFloat(vb)||0; }}
    const c = va<vb?-1:va>vb?1:0;
    return sortDir==='asc'?c:-c;
  }});

  let cT=0, cY=0, cM=0, pY='', pM='', fAll=0, fTrain=0, fCar=0, fMetro=0, fLunch=0;
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  rows.forEach((r,i) => {{
    const full=parseFloat(r.full)||0;
    if (r.year  !== pY) {{ cY=0; pY=r.year;  }}
    if (r.month !== pM) {{ cM=0; pM=r.month; }}
    cT+=full; cY+=full; cM+=full; fAll+=full;
    fTrain+=parseFloat(r.train)||0; fCar+=parseFloat(r.car)||0;
    fMetro+=parseFloat(r.metro)||0; fLunch+=parseFloat(r.lunch)||0;
    const tr=document.createElement('tr');
    tr.innerHTML=`
      <td class="num">${{i+1}}</td>
      <td>${{r.purchase_date}}</td>
      <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis">${{r.route}}</td>
      <td>${{r.travel_date}}</td>
      <td>${{r.return_date||'—'}}</td>
      <td class="r train">${{fmt(r.train)}} €</td>
      <td class="r car"  >${{fmt(r.car)}}   €</td>
      <td class="r metro">${{fmt(r.metro)}}  €</td>
      <td class="r lunch">${{fmt(r.lunch)}}  €</td>
      <td class="r full" >${{fmt(r.full)}}   €</td>
      <td class="r cm"   >${{fmt(cM)}} €</td>
      <td class="r cy"   >${{fmt(cY)}} €</td>
      <td class="r ct"   >${{fmt(cT)}} €</td>`;
    tbody.appendChild(tr);
  }});
  if (!rows.length) tbody.innerHTML='<tr><td colspan="13" class="empty">Aucun résultat</td></tr>';

  document.getElementById('tfoot').innerHTML=`<tr>
    <td colspan="5"><strong>Total (${{rows.length}} billet(s))</strong></td>
    <td class="r train">${{fmt(fTrain)}} €</td>
    <td class="r car"  >${{fmt(fCar)}}   €</td>
    <td class="r metro">${{fmt(fMetro)}}  €</td>
    <td class="r lunch">${{fmt(fLunch)}}  €</td>
    <td class="r full" >${{fmt(fAll)}}    €</td>
    <td colspan="2"></td>
    <td class="r ct"   >${{fmt(fAll)}} €</td></tr>`;

  document.querySelectorAll('th[data-col]').forEach(th => {{
    th.classList.remove('sorted-asc','sorted-desc');
    if (th.dataset.col===sortCol) th.classList.add('sorted-'+sortDir);
  }});
}}

// ── Events ────────────────────────────────────────────────────────────────────
document.getElementById('search').addEventListener('input', e=>{{ search=e.target.value; render(); }});
document.getElementById('f-year').addEventListener('change', e=>{{
  fYear=e.target.value; fMonth=''; document.getElementById('f-month').value=''; render();
}});
document.getElementById('f-month').addEventListener('change', e=>{{ fMonth=e.target.value; render(); }});
document.getElementById('sort-field').addEventListener('change', e=>{{ sortCol=e.target.value; render(); }});
document.getElementById('sort-dir').addEventListener('change',   e=>{{ sortDir=e.target.value; render(); }});
document.querySelectorAll('th[data-col]').forEach(th => th.addEventListener('click', () => {{
  const col=th.dataset.col;
  if (sortCol===col) sortDir=sortDir==='asc'?'desc':'asc';
  else {{ sortCol=col; sortDir='asc'; }}
  document.getElementById('sort-field').value=sortCol;
  document.getElementById('sort-dir').value=sortDir;
  render();
}}));

// ── Init ──────────────────────────────────────────────────────────────────────
buildFilters(); buildTabs();
renderYearChart(); renderMonthChart('all');
render();
</script>
</body>
</html>"""

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Rapport généré : {report_file}")
