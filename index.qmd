---
title: "Analyse des dépenses SNCF"
subtitle: "Outil d'analyse des déplacements Lessard-et-le-Chêne ↔ Paris"
date: today
lang: fr
---

Ce projet analyse automatiquement les confirmations de réservation **SNCF Connect** pour calculer le coût réel de chaque déplacement entre Lessard-et-le-Chêne et Paris.

## Coûts pris en compte

| Poste | Détail | Tarif 2025 |
|-------|--------|-----------|
| 🚄 **Train** | Billet SNCF Connect | Variable |
| 🚗 **Voiture** | Lessard-et-le-Chêne → Gare de Lisieux (13,5 km) | 0,548 €/km |
| 🚇 **Métro** | Saint-Lazare ↔ Saint-Denis Université (ligne 13, zones 1-3) | 2,50 €/trajet |
| 🍽️ **Repas** | Déjeuner sur place | 15,00 € |

## Fonctionnalités

- Récupération automatique des mails depuis Gmail via **OAuth2**
- **Cache local** : seuls les nouveaux mails sont téléchargés à chaque lancement
- Rapport HTML interactif : tri, filtres, recalcul des tarifs en temps réel
- Cumuls par mois, par année et depuis le début

## Documents

::: {.grid}

::: {.g-col-6}
### [Guide utilisateur](doc_utilisateur.html)

Comment installer, configurer et utiliser l'outil. Explique les règles de calcul et le fonctionnement du rapport.
:::

::: {.g-col-6}
### [Documentation technique](doc_technique.html)

Architecture du code, description des modules, diagrammes de flux et de séquence.
:::

:::

## Structure du projet

```
billets-sncf/
├── sncf_report.py          # module partagé (coûts + HTML)
├── fetch_and_report.py     # récupération Gmail (OAuth2 + cache)
├── report_local.py         # traitement fichiers .eml locaux
├── _quarto.yml             # configuration du site
├── index.qmd               # cette page
├── doc_utilisateur.qmd     # guide utilisateur
├── doc_technique.qmd       # documentation technique
└── docs/                   # site généré → GitHub Pages
```

## Lancement rapide

Un seul script à exécuter — la source est choisie automatiquement :

```bash
python3 fetch_and_report.py
```

- Si le dossier `mails/` contient des `.eml` → traitement local, sans connexion réseau
- Sinon → connexion Gmail via OAuth2 avec cache local
