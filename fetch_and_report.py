#!/usr/bin/env python3
"""
Récupère les mails SNCF Connect depuis Gmail via OAuth2 (Gmail API),
extrait les montants et génère un rapport HTML avec cumuls par année/mois.

Le cache (email_cache.json) enregistre chaque mail par son Message-ID ;
les prochains lancements ne téléchargent que les nouveaux messages.

Prérequis (une seule fois) :
  1. https://console.cloud.google.com/ → nouveau projet
  2. APIs & Services → Bibliothèque → activer "Gmail API"
  3. APIs & Services → Identifiants → Créer → ID client OAuth 2.0 → Application de bureau
  4. Télécharger le JSON → le renommer "credentials.json" dans ce dossier
  5. Lancer ce script : le navigateur s'ouvre pour autoriser l'accès
     (le token est sauvegardé dans token.json pour les prochaines fois)
"""

import os
import sys
import json
import base64
import email as emaillib
from collections import defaultdict

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    print("Installez : pip3 install google-auth-oauthlib google-api-python-client")
    sys.exit(1)

import sncf_report as R

DIR          = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS  = os.path.join(DIR, "credentials.json")
TOKEN_FILE   = os.path.join(DIR, "token.json")
CACHE_FILE   = os.path.join(DIR, "email_cache.json")
REPORT_FILE  = os.path.join(DIR, "billets_sncf_rapport.html")
SCOPES       = ["https://www.googleapis.com/auth/gmail.readonly"]
SENDER       = "noreply@connect.sncf"
SUBJECT_PREF = "Votre voyage"

# ── Cache ─────────────────────────────────────────────────────────────────────

def load_cache():
    """Retourne {message_id: trip_dict} depuis le fichier de cache."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# ── Auth OAuth2 ───────────────────────────────────────────────────────────────

def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS):
                print(f"\nFichier manquant : {CREDENTIALS}")
                print("\nPour créer les identifiants OAuth2 :")
                print("  1. https://console.cloud.google.com/ → nouveau projet")
                print("  2. APIs & Services → Bibliothèque → activer 'Gmail API'")
                print("  3. APIs & Services → Identifiants → Créer → ID client OAuth")
                print("     Type : Application de bureau")
                print(f"  4. Télécharger le JSON → le placer ici :\n     {CREDENTIALS}")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"Token sauvegardé : {TOKEN_FILE}")
    return creds

# ── Helpers Gmail ─────────────────────────────────────────────────────────────

def decode_part(part):
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

def get_plain_text(payload):
    if payload.get("mimeType") == "text/plain":
        return decode_part(payload)
    for part in payload.get("parts", []):
        result = get_plain_text(part)
        if result:
            return result
    return ""

def parse_message(msg, gmail_id):
    """Extrait un trip_dict depuis un message Gmail API complet."""
    headers  = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    msg_id   = headers.get("Message-ID") or gmail_id
    subject  = R.decode_header_str(headers.get("Subject", ""))
    date_str = headers.get("Date", "")
    plain    = get_plain_text(msg["payload"])
    amount   = R.extract_amount(plain)

    try:
        dt = emaillib.utils.parsedate_to_datetime(date_str)
        purchase_date = dt.strftime("%Y-%m-%d")
        year  = dt.strftime("%Y")
        month = dt.strftime("%Y-%m")
    except Exception:
        purchase_date = year = month = ""

    route, travel_date, return_date = R.parse_subject(subject)
    return msg_id, {
        "subject": subject, "purchase_date": purchase_date,
        "year": year, "month": month, "route": route,
        "travel_date": travel_date, "return_date": return_date,
        "amount": amount,
    }

# ── Fetch Gmail API avec cache ────────────────────────────────────────────────

def fetch_emails(service):
    cache = load_cache()
    cached_count = len(cache)

    # Lister tous les Message-IDs correspondant à la requête
    query = f'from:{SENDER} subject:"{SUBJECT_PREF}"'
    print(f"Recherche : {query}")

    refs, page_token = [], None
    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token
        result = service.users().messages().list(**kwargs).execute()
        refs.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    print(f"{len(refs)} message(s) trouvé(s) sur Gmail.")

    # Identifier les Gmail IDs déjà en cache (on cherche dans les valeurs)
    cached_gmail_ids = {v.get("_gmail_id") for v in cache.values() if v.get("_gmail_id")}

    to_fetch = [r for r in refs if r["id"] not in cached_gmail_ids]
    print(f"  {cached_count} en cache  ·  {len(to_fetch)} à télécharger")

    new_count = 0
    for i, ref in enumerate(to_fetch):
        msg = service.users().messages().get(
            userId="me", id=ref["id"], format="full"
        ).execute()

        msg_id, trip = parse_message(msg, ref["id"])
        trip["_gmail_id"] = ref["id"]

        if msg_id not in cache:
            cache[msg_id] = trip
            new_count += 1

        if (i + 1) % 10 == 0 or (i + 1) == len(to_fetch):
            print(f"  téléchargé {i+1}/{len(to_fetch)}…")

    if new_count:
        save_cache(cache)
        print(f"Cache mis à jour : {new_count} nouveau(x) mail(s) ajouté(s) → {CACHE_FILE}")
    else:
        print("Cache à jour, aucun nouveau mail.")

    # Retourner tous les trips (cache complet), triés par date
    trips = list(cache.values())
    # Éliminer les doublons potentiels sur _gmail_id
    seen_gids = set()
    deduped = []
    for t in trips:
        gid = t.get("_gmail_id", id(t))
        if gid not in seen_gids:
            seen_gids.add(gid)
            deduped.append(t)
    deduped.sort(key=lambda x: x.get("purchase_date", ""))
    return deduped

# ── Résumé console ────────────────────────────────────────────────────────────

def print_summary(trips):
    total_train = sum(t["amount"] or 0 for t in trips)
    total_car   = sum(t["car"]          for t in trips)
    total_metro = sum(t["metro"]        for t in trips)
    total_lunch = sum(t["lunch"]        for t in trips)
    total_all   = sum(t["full"]         for t in trips)

    by_year  = defaultdict(float)
    by_month = defaultdict(float)
    for t in trips:
        if t.get("year"):  by_year[t["year"]]   += t["full"]
        if t.get("month"): by_month[t["month"]]  += t["full"]

    print(f"\n{len(trips)} billets")
    print(f"  Train       : {total_train:9.2f} €")
    print(f"  Voiture     : {total_car:9.2f} €  ({R.DISTANCE_KM} km × {R.RATE_KM} €/km)")
    print(f"  Métro       : {total_metro:9.2f} €  ({R.METRO_TICKET} €/trajet)")
    print(f"  Repas       : {total_lunch:9.2f} €  ({R.LUNCH_COST} €/jour)")
    print(f"  ─────────────────────────────────────────")
    print(f"  TOTAL       : {total_all:9.2f} €\n")

    print("── Par année (coût total) ──────────────────────────────")
    cumul = 0
    for y in sorted(by_year):
        cumul += by_year[y]
        print(f"  {y} : {by_year[y]:9.2f} €   (cumul : {cumul:.2f} €)")

    print("\n── Par mois (coût total) ───────────────────────────────")
    cumul = 0
    for m in sorted(by_month):
        cumul += by_month[m]
        print(f"  {m} : {by_month[m]:9.2f} €   (cumul : {cumul:.2f} €)")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Billets SNCF — Récupération via Gmail API (OAuth2)")
    print("=" * 60)

    creds   = get_credentials()
    service = build("gmail", "v1", credentials=creds)
    trips   = fetch_emails(service)

    if not trips:
        print("Aucun billet trouvé.")
        sys.exit(0)

    for t in trips:
        car, metro, lunch = R.compute_extra(t)
        t["car"] = car; t["metro"] = metro; t["lunch"] = lunch
        t["extra"] = round(car + metro + lunch, 2)
        t["full"]  = round((t["amount"] or 0) + t["extra"], 2)

    print_summary(trips)
    R.generate_html(trips, REPORT_FILE)

    import subprocess
    subprocess.Popen(["open", REPORT_FILE])

if __name__ == "__main__":
    main()
