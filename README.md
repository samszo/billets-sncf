# Analyse des dépenses SNCF

Outil d'analyse des déplacements domicile-travail **Lessard-et-le-Chêne ↔ Paris**, à partir des confirmations de réservation SNCF Connect.

📖 **Documentation complète** : [samszo.github.io/billets-sncf](https://samszo.github.io/billets-sncf)

---

## Démarche

### Problème

Les billets SNCF ne représentent qu'une partie du coût réel d'un déplacement. Pour mesurer précisément ce que coûte chaque journée de travail à Paris, il faut additionner quatre postes :

| Poste | Détail |
|-------|--------|
| 🚄 Train | Billet SNCF Connect (variable) |
| 🚗 Voiture | Lessard-et-le-Chêne → Gare de Lisieux, 13,5 km, 0,548 €/km (barème fiscal 2025) |
| 🚇 Métro | Saint-Lazare ↔ Saint-Denis Université, ligne 13, zones 1-3, 2,50 €/trajet |
| 🍽️ Repas | Déjeuner sur place, 15 € |

La distance kilométrique a été calculée via [OSRM](http://router.project-osrm.org/) (OpenStreetMap). Le taux kilométrique est le barème officiel DGFIP 2025 pour un véhicule 5 CV fiscal, tranche 0–5 000 km/an.

### Solution

1. **Collecter** les mails de confirmation SNCF Connect — soit depuis Gmail (OAuth2 + cache), soit depuis des fichiers `.eml` exportés localement.
2. **Extraire** le montant du billet (`Total commande : X,XX €`) par expression régulière dans le corps texte du mail.
3. **Calculer** les frais annexes selon la direction du trajet (Lisieux → Paris ou retour) et la présence d'un aller-retour dans le même billet.
4. **Produire** un rapport HTML interactif avec cumuls par mois et par année, filtres et recalcul à la volée des tarifs.

### Règles de calcul des frais annexes

```
Lisieux → Paris (aller + retour même billet)
  Voiture : 2 × 13,5 km × 0,548 €/km = 14,80 €
  Métro   : 2 × 2,50 €               =  5,00 €
  Repas   :                             15,00 €

Lisieux → Paris (aller seul)
  Voiture : 1 × 13,5 km × 0,548 €/km =  7,40 €
  Métro   : 1 × 2,50 €               =  2,50 €
  Repas   :                             15,00 €

Paris → Lisieux (retour acheté séparément)
  Voiture : 1 × 13,5 km × 0,548 €/km =  7,40 €
  Métro   : 1 × 2,50 €               =  2,50 €
  Repas   :                              0,00 €  ← retour à domicile
```

---

## Utilisation

### Prérequis

```bash
python3 --version   # 3.9+
pip3 install google-auth-oauthlib google-api-python-client  # pour le mode Gmail
```

### Lancer l'analyse

```bash
python3 fetch_and_report.py
```

Le script choisit automatiquement la source :

- **`mails/` contient des `.eml`** → traitement local, aucune connexion réseau
- **`mails/` vide ou absent** → connexion Gmail via OAuth2 avec cache local (`email_cache.json`)

### Mode Gmail — configuration initiale

1. [console.cloud.google.com](https://console.cloud.google.com/) → nouveau projet
2. APIs & Services → Bibliothèque → activer **Gmail API**
3. Identifiants → Créer → **ID client OAuth 2.0** → Application de bureau
4. Télécharger le JSON → le renommer **`credentials.json`** dans ce dossier
5. Premier lancement : un navigateur s'ouvre pour autoriser l'accès (token sauvegardé ensuite dans `token.json`)

### Modifier les tarifs

Éditez les constantes au début de `sncf_report.py` :

```python
DISTANCE_KM   = 13.5    # km aller : Lessard-et-le-Chêne → Gare de Lisieux
RATE_KM       = 0.548   # €/km — barème kilométrique 2025, 5 CV, < 5 000 km/an
METRO_TICKET  = 2.50    # €/trajet — zones 1-3, ligne 13 (2025)
LUNCH_COST    = 15.00   # € — repas du midi
```

Les paramètres sont aussi modifiables directement dans le rapport HTML sans relancer Python.

---

## Structure du projet

```
billets-sncf/
├── sncf_report.py          # module partagé : calcul des coûts + génération HTML
├── fetch_and_report.py     # point d'entrée unique (local ou Gmail)
├── mails/                  # déposer les .eml ici pour le mode local
├── _quarto.yml             # configuration du site de documentation
├── index.qmd               # page d'accueil
├── doc_utilisateur.qmd     # guide utilisateur (Quarto + Mermaid)
├── doc_technique.qmd       # documentation technique (Quarto + Mermaid)
└── docs/                   # site statique généré → GitHub Pages
```

Fichiers générés automatiquement, exclus du dépôt (`.gitignore`) :

| Fichier | Contenu |
|---------|---------|
| `credentials.json` | Identifiants OAuth2 Google (**secret**) |
| `token.json` | Token d'accès Gmail (**secret**) |
| `email_cache.json` | Cache des mails téléchargés |
| `billets_sncf_rapport.html` | Rapport HTML généré |

---

## Mettre à jour la documentation

```bash
quarto render          # régénère docs/
git add docs/
git commit -m "Update docs"
git push               # publie sur GitHub Pages
```

---

## Licence

Usage personnel.
