# Journal des décisions : matière première du rapport

Ce fichier est complété au fil du projet. Chaque décision est notée avec sa justification, rangée dans la section du rapport où elle sera utilisée (structure du sujet : Introduction, Méthodologie, État de l'art, Résultats et discussion, Conclusion et perspectives).

Convention : **[fait]** = réalisé et vérifié, **[prévu]** = décidé mais pas encore implémenté, **[à valider]** = à confirmer en équipe.

---

## 1. Introduction

- **Problème** : automatiser, avec des agents spécialisés, la chaîne données → entraînement → validation → déploiement d'un modèle, avec des critères de promotion explicites et une approbation humaine avant la production.
- **Exigence ajoutée par l'encadrant** : le pipeline doit traiter n'importe quel dataset d'apprentissage supervisé, détecter le type de tâche, proposer des algorithmes et entraîner le modèle. **[fait]**
- **Liberté de conception laissée par l'encadrant** : agents à scripts ou agents avec LLM, au choix de l'équipe. **[fait]**
- **Périmètre retenu** : données tabulaires (CSV), apprentissage supervisé (classification binaire, multiclasse, régression). Hors périmètre : images, texte, audio, séries temporelles, non supervisé.
  - *Justification* : le travail évalué porte sur le pipeline (agents, gate, déploiement, CI/CD, comparaison), pas sur la couverture de tous les types de données. Un périmètre borné est plus crédible qu'une universalité qu'on ne pourrait pas démontrer.
- **Organisation** : équipe de trois, un bloc complet par personne (voir `CONTRACT.md`, section 2).

## 2. Méthodologie

### 2.1 Infrastructure
- **Stockage objet : Silo (fork communautaire de MinIO)** **[fait]**
  - *Justification* : MinIO a cessé de distribuer ses images communautaires ; l'image `minio/minio` n'est plus téléchargeable. Silo conserve l'API S3 et les variables `MINIO_*`, donc le code (`boto3`, MLflow) n'a pas changé. Contrainte réelle de l'écosystème, à documenter.
- **Suivi d'expériences : MLflow**, artefacts stockés dans MinIO (`s3://mlflow/`). **[fait]**
- **Orchestration locale : Docker Compose** pour le développement ; Kubernetes réservé au déploiement final. *Justification* : reproductible en une commande sur la machine de chaque membre, sans cluster pour développer.
- **Un seul module de connexion S3** (`core/storage.py`) : les dépôts passent par `upload_file` (via un fichier temporaire), avec délais d'attente et reprises sur une nouvelle connexion. *Justification* : sur cet environnement (Silo sous Docker Desktop, Windows), `put_object` et `upload_fileobj` avec threads échouaient (délai dépassé ou connexion coupée), alors que `upload_file` fonctionnait. La cause exacte côté serveur ou réseau n'a pas été élucidée ; le diagnostic est reproductible avec `scripts/diag_s3.py`. **[fait]**

### 2.2 Architecture des agents
- **Quatre agents** (Data, Training, QA, Release) + orchestrateur LangGraph + quality gate + approbation humaine, selon la chaîne du sujet. **[prévu]**
- **Règle de sécurité** : chaque agent n'a accès qu'à ses outils ; seul l'agent Release modifie le cluster, et uniquement après approbation humaine (précondition vérifiée dans le code). **[prévu]**
- **Approche hybride scripts + LLM** **[à valider côté fournisseur LLM]**
  - Des outils déterministes font le travail ; le LLM propose des algorithmes à partir du **profil** du dataset (jamais des données brutes) et justifie ses choix.
  - Sa sortie est validée contre une **liste blanche** d'algorithmes ; **repli automatique** sur des règles s'il échoue ; il n'a aucun accès au cluster ni au registre.
  - *Justification* : sécurité, reproductibilité, coût maîtrisé, et une différence mesurable entre pipeline agentique et pipeline classique.
- **Contrat d'interfaces partagé** (`core/contract.py`, `docs/CONTRACT.md`) : état partagé typé, une section par agent, décisions cumulées pour la traçabilité. *Justification* : permet à trois personnes de travailler en parallèle sans se bloquer. **[fait]**

### 2.3 Choix de rigueur en apprentissage automatique
- **Prétraitement dans le Pipeline scikit-learn**, pas dans l'Agent Data : l'imputation, l'encodage et la mise à l'échelle sont appris sur le jeu d'entraînement seul. *Justification* : éviter la fuite d'information du jeu de test vers l'entraînement. L'Agent Data se limite aux opérations sans fuite (doublons, colonnes constantes ou de type identifiant, valeurs invalides). **[prévu]**
- **Découpage train/test unique** (`core/split.py`) : graine 42, 20 % de test, stratification pour la classification ; Training et QA l'appellent tous les deux. *Justification* : même jeu de test pour l'entraînement et la validation, résultats reproductibles. Si une classe a moins de 2 exemples, la fonction échoue explicitement plutôt que de contourner en silence. **[fait]**
- **Reproductibilité** : graines fixées, dépendances figées, versionnement du dataset par empreinte (hash SHA-256) dans MinIO, commit Git enregistré dans les métadonnées du modèle. **[prévu]**
- **Détection de la tâche** : cible numérique à nombreuses valeurs → régression ; cible textuelle, booléenne ou numérique à peu de valeurs → classification. Les cas ambigus sont signalés, jamais tranchés en silence. La colonne cible est fournie dans `dataset.yaml` ; sans fichier, elle est proposée par heuristique et confirmée par l'humain. *Justification* : la détection automatique de la cible n'est pas fiable. **[prévu]**

### 2.4 Quality gate
- **Critères relatifs, pas absolus** : le modèle doit battre un modèle trivial (classe majoritaire ou moyenne), ne pas régresser par rapport au modèle en production, rester robuste au bruit, et respecter un seuil d'équité si des colonnes sensibles sont déclarées. *Justification* : un seuil absolu comme « F1 > 0,80 » n'a aucun sens sur un dataset arbitraire. Les seuils initiaux sont à calibrer sur les datasets de test. **[prévu]**
- **Approbation humaine toujours requise** avant la production, conformément à la règle de sécurité du sujet, même si le gate est favorable. **[prévu]**

### 2.5 Datasets de test
| Dataset | Tâche | Pourquoi |
|---|---|---|
| Adult Income | classification binaire | valeurs manquantes (workclass, occupation, native-country), doublons, classes déséquilibrées, attributs sensibles pour l'équité |
| Wine | classification multiclasse | cible entière à 3 valeurs : cas où la détection de tâche ne doit pas se tromper avec une régression |
| Diabetes | régression | cible continue, sans valeurs manquantes |
| California Housing | régression | volume plus important (environ 20 000 lignes) |

Constats mesurés sur Adult (48 842 lignes) **[fait]** : 2 799 valeurs manquantes dans `workclass`, 2 809 dans `occupation`, 857 dans `native-country` ; 52 doublons ; classe `>50K` à 23,9 % ; part de `>50K` de 10,9 % chez les femmes contre 30,4 % chez les hommes. Cet écart provient des données de 1994 et fournit un cas concret pour le test d'équité.

### 2.6 Déploiement et CI/CD
- **API de serving générique** : le modèle embarque son préprocesseur et un `schema.json` ; l'API lit le schéma dans les métadonnées, donc elle ne contient aucune logique propre à un dataset. **[prévu]**
- **Pipeline en deux phases** (décision ouverte) : Phase A déclenchée par la CI/CD (data → training → QA → gate, état sauvegardé en attente d'approbation) ; Phase B déclenchée après clic dans l'IHM (release). *Raison* : un job CI ne peut pas attendre l'humain pendant des heures, et un runner hébergé n'atteint pas le `localhost` de nos machines. **[à valider avec Clement]**

### 2.7 Protocole de comparaison agentique vs non agentique
- **Baseline** : les mêmes fonctions de `core/` enchaînées par un script, algorithme fixe, sans orchestrateur, sans LLM, sans gate. *Justification* : comparaison équitable, seule la couche agentique change.
- **Mesures**, sur au moins trois datasets et avec la même graine : qualité du modèle sur le même jeu de test, temps total, problèmes détectés et empêchés d'atteindre la production, traçabilité, effort humain.
- *Valorisation* : cette comparaison rigoureuse peut faire l'objet d'un article scientifique, selon le sujet.

## 3. État de l'art (à documenter)

Pistes de recherche bibliographique à compléter :
- MLOps : cycle de vie, registre de modèles, quality gates, déploiement progressif et rollback.
- Outils : MLflow, DVC, Kubeflow, Evidently, Fairlearn, Great Expectations.
- Orchestration d'agents : LangGraph, CrewAI ; agents LLM avec outils et garde-fous.
- AutoML : auto-sklearn, FLAML, AutoGluon. *Pourquoi les citer* : ils répondent aussi à « proposer un algorithme et entraîner », donc ils servent de point de comparaison.
- Équité : métriques (parité démographique, égalité des chances), jeu de données Adult dans la littérature.

## 4. Résultats et discussion

À remplir avec les mesures du protocole 2.7, un tableau par dataset.

## 5. Conclusion et perspectives

À remplir. Limites déjà identifiées : périmètre tabulaire, seuils du gate à calibrer, dépendance au fournisseur LLM, environnement de déploiement local plutôt que cloud.

---

## Journal des incidents (utile pour la discussion)

| Date | Incident | Cause | Résolution |
|---|---|---|---|
| 2026-11-05 | Échec du build Docker (`pip`, hash non conforme) | Téléchargement interrompu et images trop lourdes | Délais et reprises ajoutés ; séparation des images par composant |
| 2026-11-05 | `pull access denied for minio/minio` | Image retirée de Docker Hub | Passage à Silo |
| 2026-11-05 et 2026-11-21 | Dépôts vers Silo bloqués (`ReadTimeoutError`) ou coupés (`ConnectionClosedError`), de façon intermittente | **Non élucidée.** Mesuré : `put_object` et `upload_fileobj` (threads) échouent ; `upload_file` et `upload_fileobj` sans threads réussissent (2 essais chacun). Le journal de Silo ne montre aucune erreur. | `write_bytes` utilise `upload_file` avec délais et reprises ; outil de diagnostic `scripts/diag_s3.py` |
