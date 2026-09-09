# Radar TIC · Catalunya i Govern Balear

Radar executiu per consultar oportunitats, adjudicacions, antecedents i notícies. Portada adaptada a mòbil, dos àmbits, seguiment local, compte enrere, dossiers visuals i PDF compartible.

## Publicar a GitHub, pas a pas

1. Descomprimeix **Radar-TIC-GitHub.zip**. Obre la carpeta `radar-tic`.
2. A GitHub, crea un repositori públic nou, per exemple **radar-tic-pro**, amb branca **main**. Així conserves el radar anterior.
3. A **Add file → Upload files**, arrossega el contingut de la carpeta: `site`, `scripts`, `tests`, `requirements.txt` i `README.md`. Fes **Commit changes**. Si el navegador limita el nombre de fitxers, puja les carpetes per separat. No pugis el ZIP com un únic fitxer.
4. A **Add file → Create new file**, escriu `.github/workflows/radar.yml`. Copia el contingut del fitxer del mateix nom inclòs al paquet. Fes **Commit changes**. Aquest pas és necessari si la carpeta oculta `.github` no s’ha pujat.
5. A **Settings → Pages → Build and deployment → Source**, tria **GitHub Actions**.
6. A **Actions → Actualitza i publica Radar TIC → Run workflow**, tria **main** i executa'l. Si GitHub demana activar Actions, activa'l.
7. Espera que **build** i **deploy** acabin en verd. A **Settings → Pages** trobaràs l’adreça de la web. La primera importació pot trigar diversos minuts.
8. Comprova la portada, el filtre **Local + Balears**, els SDA, un PDF i un enllaç de dossier compartit. L’enllaç compartit funcionarà per als companys després de publicar la web.

No cal cap clau API. No s'ha publicat aquest projecte ni s'ha modificat el repositori original.

## Ús diari

- **Avui** mostra oportunitats amb termini vigent. Les suspeses queden fora. Els dies i hores es calculen amb l’hora de Madrid; quan venç el termini, la fitxa passa a pendent d’adjudicació.
- **Generalitat** agrupa departaments i organismes. **Local + Balears** agrupa ajuntaments, diputacions, ens locals tecnològics, Govern Balear i sector instrumental, inclosa Fundació BIT. El selector de territori permet separar Catalunya i Balears.
- **SDA** integra els avisos del tauler i les dades obertes. El recompte d’avisos és diferent del de lots i expedients. Les categories es poden filtrar.
- Un clic obre el **dossier**. Permet descarregar PDF, copiar l’enllaç, preparar un correu o compartir el PDF si el dispositiu ho admet. En altres navegadors descarrega el PDF perquè el puguis adjuntar.
- Les **estrelles** es desen al navegador. **Notícies** recupera titulars i enllaços a fonts oficials. **RSS** permet seguir novetats amb un lector.
- **Recarrega** comprova la versió publicada. La recopilació de fonts s’executa automàticament tres cops al dia; també es pot iniciar amb **Run workflow**.

## Horaris i manteniment

La programació és a les 05:17, 11:17 i 17:17 UTC: 07:17, 13:17 i 19:17 a l’estiu; 06:17, 12:17 i 18:17 a l’hivern. GitHub pot retardar execucions. Si un pas falla, es conserva l’última web publicada: obre Actions i revisa el pas vermell abans de repetir-lo. GitHub pot desactivar la programació d’un repositori públic després de 60 dies sense activitat; es reactiva des d’Actions.

Les execucions programades despleguen les dades a Pages i les guarden a la memòria cau d’Actions; no fan commits de dades al repositori. L’històric inicial de Balears ja està inclòs, no has de baixar els arxius estatals complets.

## Fonts i comprovació

Catalunya: dades obertes PSCP des de 2022, publicacions estructurades i taulers SDA. Balears: PLACSP des de 2025 i directori oficial de contractants, filtrat per dependència del Govern, no només per ubicació. Els prefixos CPV TIC configurats són 302, 48, 72, 322, 324, 325, 642, 5031, 5032, 5131, 5161 i 3012.

Els lots conserven la seva identitat i els imports són sense IVA. El valor estimat, les pròrrogues i les modificacions es mantenen separats. Un guió significa que no s’ha extret la dada. No s’aplica un 20% per defecte.

La diferència aritmètica entre pressupost i adjudicació no es presenta com una baixa documentalment acreditada. Els antecedents són candidats; no s’atribueix un incumbent per semblança de títol o CPV. Les fonts queden dins el detall desplegable del dossier.

Cada execució amplia fins a 240 publicacions estructurades i 100 dossiers PDF, conservant la memòria cau. El detall disponible depèn del format i l’accessibilitat del plec. Una revisió manual de subcriteris s’associa al hash del PDF perquè no es reutilitzi en una versió diferent. No és una lectura universal de tots els plecs.

L’inventari privat només s’ha utilitzat per identificar denominacions d’organismes. El paquet no conté telèfons, adreces de seus ni informació personal de l’inventari.

## Prova local

Amb Python instal·lat, des de la carpeta del projecte:

```text
python -m http.server 8765 --directory site
```

Obre `http://localhost:8765`. No obris l’HTML amb doble clic: el navegador bloqueja la càrrega de dades locals. La recopilació completa s’executa amb els passos del workflow inclòs. Les proves són `python -m unittest discover -s tests -v` i `node tests/test_core.mjs`.

Els canvis pujats al repositori publiquen les dades disponibles, sense repetir la recopilació. Les execucions programades i Run workflow sí que actualitzen les fonts. La comprovació de Pages es fa al principi.
