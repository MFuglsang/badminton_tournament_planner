# Brugervejledning: Afviklingssiden

Afviklingssiden er din primære arbejdsflade på selve turneringsdagen. Den giver dig et samlet overblik over alle kampe, aktive kampe og de næste kampe der skal startes.

---

## Sidens opbygning

Siden er opdelt i to kolonner:

- **Venstre kolonne** — alle rækker med deres kampe
- **Højre kolonne (sidebar)** — de kampe der er i gang lige nu, de næste kampe der skal startes, og genveje

Øverst på siden vises en **fremgangslinje** der viser hvor mange kampe der er afviklet ud af det samlede antal.

---

## Fremgangslinje

```
24 / 60 kampe afviklet        3 i gang
████████░░░░░░░░░░░░░░░
```

- Det **grønne felt** vokser efterhånden som kampe afsluttes
- Når alle kampe er afviklet vises: **✓ Alle kampe afviklet**

---

## Søgning

Øverst i venstre kolonne er der et søgefelt. Du kan søge på:

- **Kampnummer** — f.eks. `#42`
- **Spillernavn eller parnavn** — f.eks. `Hansen`

Matchende kampe fremhæves med gul baggrund på tværs af alle rækker.

---

## Rækker (venstre kolonne)

Hver række kan foldes ud og ind ved at klikke på dens header. Headeren viser:

| Element | Betydning |
|---|---|
| Rækkenavn | Navn på disciplinen, f.eks. "Mixed Double A" |
| Disciplin | Singles, Double osv. |
| 🔵 **X i gang** | Antal kampe der er startet, men ikke afsluttet |
| 🟡 **X venter** | Antal kampe der mangler at blive startet |
| 🟢 **X færdige** | Antal afsluttede kampe |
| ✓ **Færdig** | Alle kampe i rækken er afviklet |

### Faner inde i en række

Når en række er foldet ud, kan du skifte mellem tre faner:

#### Kampe
Viser alle ventende og igangværende kampe i rækken.

For hver kamp vises:
- **#nummer** og planlagt tidspunkt
- **Spillere/par** med evt. seedning og statusikoner
- **Knapper** til at starte eller registrere resultat

Statusikoner ved spillernavne:
- 🏸 — spilleren er i gang med en anden kamp
- ⚠ **Optaget** — vises i stedet for Start-knap hvis en spiller er optaget eller i hvile

Afsluttede kampe er foldet væk under **"Afsluttede kampe (X)"** og kan foldes ud ved behov. Her kan resultater rettes.

#### Stilling
Viser den aktuelle stilling i rækken (gruppespil/slutspil).

Kolonner: Spillede (S), Vundet (V), Tabt (T), Point (Pt), Sæt og Score.

En grøn pil ↑ viser hvilke hold der avancerer til slutspillet.

Statusprikker:
- 🟢 — spiller er i gang med en kamp
- 🟡 — spiller er i hvile

#### Spilletræ / Slutspil
Viser bracket-visning for rækker med udskilningskampe.

---

## Sidebar (højre kolonne)

### ⚡ Kampe i gang
Vises kun hvis der er aktive kampe. For hver igangværende kamp kan du direkte:
- Klikke **Resultat** for at registrere udfaldet
- Klikke **WO** for at registrere en walkover

### 🏸 Næste kampe
Viser de op til 5 næste ventende kampe (sorteret på tidspunkt), hvor ingen af spillerne er optaget. Klik **▶ Start** for at starte en kamp direkte herfra.

---

## Typisk arbejdsgang på turneringsdagen

1. **Åbn afviklingssiden** og hold den åben i browseren hele dagen
2. **Se sidebar → Næste kampe** for at finde hvem der skal på banen
3. Klik **▶ Start** på den pågældende kamp
4. Når kampen er slut: gå til **⚡ I gang** og klik **Resultat**
5. Registrer resultatet — siden opdateres automatisk hvert 60. sekund
                    
---

## Storskærm

Klik **📺 Storskærm** øverst på siden for at åbne en storskærmsvisning i et nyt vindue. Den viser de 5 næste kampe og er optimeret til at blive vist på en ekstern skærm i hallen. Storskærmen opdaterer sig selv automatisk.

---

## Tip

- Afviklingssiden opdateres automatisk. Husk at genindlæse siden manuelt hvis du vil have de nyeste data med det samme (F5 / Cmd+R).
- Brug **søgefeltet** til hurtigt at finde en specifik kamps nummer eller et spillernavn, hvis en spiller spørger hvornår de skal spille.
- Rækkerne husker ikke hvilke der er foldet ud ved genindlæsning — fold de aktive rækker ud ved start af dagen.
