# Signature de code (SignPath)

Les exécutables Windows (`Slimgma.exe` portable, l'app dans l'installateur, et
`Slimgma-Setup-x.y.z.exe`) sont signés numériquement pendant `release.yml`
via [SignPath.io](https://signpath.io), qui fournit la signature gratuitement
aux projets open source. Tant que ce qui suit n'est pas fait, le workflow de
release échouera à l'étape de signature.

## 1. Créer le projet sur SignPath

1. Créer un compte sur https://app.signpath.io et candidater au programme
   open source (validation manuelle par SignPath, compter quelques jours).
2. Une fois approuvé, créer un projet nommé `Slimgma` (le `project-slug`
   doit correspondre exactement à celui utilisé dans
   `.github/workflows/release.yml`).
3. Dans ce projet, créer une politique de signature nommée `release-signing`
   (le `signing-policy-slug` utilisé dans le workflow) et lui associer un
   certificat de signature de code.
4. Noter l'**Organization ID** SignPath (visible dans les paramètres de
   l'organisation).
5. Générer un **API token** SignPath avec les droits de soumission de
   demandes de signature pour ce projet.

## 2. Configurer le dépôt GitHub

Dans *Settings → Secrets and variables → Actions* du dépôt :

- **Secret** `SIGNPATH_API_TOKEN` : le token généré à l'étape précédente.
- **Variable** `SIGNPATH_ORGANIZATION_ID` : l'Organization ID SignPath.

## 3. Fonctionnement

`release.yml` construit d'abord les binaires non signés, les envoie à
SignPath comme artefacts GitHub Actions, attend la signature
(`wait-for-completion: true`), puis reprend les binaires signés pour
construire et signer l'installateur :

1. `Slimgma.exe` (portable) + `dist/Slimgma/Slimgma.exe` (app utilisée par
   l'installateur) → une première demande de signature.
2. Les binaires signés remplacent les binaires non signés, l'installateur
   `.iss` est compilé avec l'app déjà signée dedans.
3. `Slimgma-Setup-x.y.z.exe` → une seconde demande de signature pour
   l'installateur lui-même.

`.github/scripts/build-installer.ps1` accepte deux options pour permettre
cette découpe :

- `-SkipCompile` : construit seulement l'app PyInstaller (`dist/Slimgma/`),
  sans lancer Inno Setup.
- `-SkipBuild` : suppose que `dist/Slimgma/` existe déjà et lance seulement
  Inno Setup.

Le workflow `build.yml` (exécuté à chaque push, hors tags) continue de
produire des exécutables **non signés** pour les tests — seul `release.yml`
signe, pour ne pas consommer le quota de signature SignPath sur chaque
commit.
