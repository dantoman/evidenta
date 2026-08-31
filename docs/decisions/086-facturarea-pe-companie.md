# ADR-086 — Câte o factură pe companie; firma de contabilitate primește una singură, pentru companiile pe care le plătește

- **Stare:** Acceptat — produs, proprietar
- **Data:** 2026-08-31
- **Decis de:** proprietarul proiectului, verbatim: *„câte o factură pe companie... și în cazul firmei
  de contabilitate este posibil să fie o factură pe toate companiile care au plata indirectă... restul
  companiilor cu plata directă au facturile lor."*
- **Închide:** `OD-107` (emiterea abonamentului), partea de **destinatar**
- **Atinge:** `plan`, `subscription`, `billing_account`, ecranul *Companii*; Spec A §10
- **Legate:** [ADR-082](082-unitatea-facturabila.md) (cantitatea),
  [ADR-085](085-spatiul-apartine-unui-utilizator.md) (spațiul e al unei persoane),
  [ADR-081](081-revendicarea-optionala.md) (canalul wholesale), `OD-120` (grila), `DN-25` (revocarea)

## 1. Ce decide, și ce nu

[ADR-082](082-unitatea-facturabila.md) a decis **cantitatea**: unitatea facturabilă e compania, iar
prețul se compune din bază plus companii × preț unitar. A spus explicit *„indiferent cine plătește"* —
deci n-a decis **destinatarul**. Acesta e destinatarul.

> **Implicit, fiecare companie primește propria factură, pe IDNO-ul ei — plată directă.**
>
> **Excepția e plata indirectă:** un plătitor — de regulă firma de contabilitate — primește **o
> singură factură** pentru **toate** companiile pe care le plătește, cu ele ca linii.
>
> **Cele două coexistă în același spațiu de lucru.** Companiile cu plată directă își păstrează
> facturile lor.

## 2. De ce implicitul nu putea fi altul

Fiecare companie e persoană juridică separată. O factură emisă pe una **nu intră în registrele
alteia**: cheltuiala se deduce de cine a consumat serviciul și pe numele cui e documentul. Un
antreprenor cu patru firme care ar primi o singură factură pe una dintre ele ar avea trei companii
fără document și una care deduce un cost ce nu e al activității ei.

Observația e a proprietarului și a răsturnat forma pe care ecranul o avea cu o oră înainte — un
„plătitor al spațiului de lucru", care presupunea tacit că spațiul e unitatea de facturare. Nu e:
spațiul e al unei persoane ([ADR-085](085-spatiul-apartine-unui-utilizator.md)), iar contabilitatea e
a companiei.

## 3. De ce excepția e reală, nu o comoditate

O firmă de contabilitate cu șaizeci de clienți nu vrea șaizeci de facturi de la furnizorul ei de
software, și nici nu are de ce: **ea consumă serviciul**, ca intrare în propriul ei serviciu. Costul e
al ei, deductibil la ea, iar mai departe îl recuperează prin onorariu sau îl absoarbe — decizia ei
comercială, în afara acestui produs.

Ce **nu** face excepția: nu dă companiei plătite indirect un document propriu. Nu are, și nici nu
trebuie — nu ea a cumpărat. Dacă un client vrea totuși factura pe numele lui, trece pe plată directă;
asta e chiar alegerea pe care modul de plată o exprimă.

## 4. Ce cere în date

Modul de plată e **al companiei**, nu al spațiului:

| Câmp | Ce ține |
|---|---|
| compania facturată | rândul e per companie chiar și când factura e comună — altfel cantitatea din ADR-082 n-are de ce se agăța |
| modul de plată | `direct` sau `indirect`; implicit `direct` |
| plătitorul | doar la `indirect`: firma care plătește. La `direct` e compania însăși, deci coloana e goală, nu redundantă |

Gruparea la emitere e o consecință, nu o a doua structură: **o factură per plătitor per perioadă**,
cu o linie per companie plătită. Pentru plata directă, plătitorul e compania, deci regula produce
exact o factură cu o linie — același mecanism, fără caz special.

**Ștampilarea rămâne cum a decis ADR-082 §4:** cantitatea și modul de plată se îngheață pe factură,
fiindcă `company.status` și modul curent nu pot răspunde despre o perioadă trecută.

## 5. Ce rămâne deschis, și unde

- **`OD-120`** — cifrele grilei și proporționalitatea la mijloc de lună. Neatinse aici.
- **`DN-25`** — ce se întâmplă cu plata indirectă când mandatul firmei încetează. Decizia de aici o
  face mai ascuțită: o companie plătită indirect rămâne, la revocare, **fără plătitor**, iar
  alternativele sunt trecerea automată pe plată directă (și atunci cine acceptă prețul?) sau
  suspendarea abonamentului. Nu se decide aici.
- **Emiterea propriu-zisă** — serie, e-Factura, TVA pe factura vendorului: `billing` nu există ca
  modul, iar dacă vendorul e rezident RM factura lui e ea însăși document fiscal moldovenesc.

## 6. Ce se construiește, și în ce ordine

Nimic din acest ADR nu e construit. **Măsurat la scriere: nu există tabelele `plan`, `subscription`
sau `billing_account` în baza vie** — sunt în Spec A și în ADR-082, nu în schemă. Prima bucată care
are sens e alegerea planului **pe rândul companiei**, în lista de companii, fiindcă acolo e și
unitatea, și modul de plată; ecranul spațiului de lucru nu mai are ce arăta despre facturare.
