# 11 — Google Stitch prompts (UI design for P6)

How to use:
1. In Stitch, start a project and paste the **Design system prompt** first.
2. Then generate each page with its prompt, once in **Mobile** and once in **Web/Desktop** mode.
3. Export each screen as code (HTML) + a screenshot (PNG) into `web/stitch/` named like
   `02-report-mobile.html`, `02-report-mobile.png`, `02-report-desktop.html`, ...
4. Tell Claude "Stitch files are in". It wires them to the real API.

Decisions: palette **A, Sage & Cream** · style **clean civic** (flat, thin borders, gently rounded,
line icons) · pages: 5 required + Dashboard, Safety guide, How it works & privacy, Business dispute.

---

## 0. Design system prompt (paste FIRST, once)

> Design a responsive web app called **"Scam Map"** for India. People use it to **check** a phone
> number, UPI ID, website link or SMS sender before trusting it, and to **report** scams anonymously.
> It must work on phones (390 px) and laptops (1280 px+).
>
> **Style: clean civic.** Calm, trustworthy, handmade-looking, like a well-designed public-service
> or banking app. Flat cream surfaces, 1 px warm borders, corner radius 12 px, generous spacing,
> simple line icons (1.75 px stroke, Lucide/Phosphor style), every icon has a text label.
> Strictly **no gradients, no purple or blue, no glassmorphism, no neon, no emoji, no 3D blobs,
> no stock "hacker in hoodie" images**. Shadows only on floating elements (bottom sheet, toasts), very soft.
>
> **Colours:** background warm cream #F6F1E4 · cards ivory #FFFDF7 · primary deep sage #4F6F52
> (header, primary buttons, active tabs) · accent muted gold #C9A227 (highlights, focus rings,
> small badges, links) · text charcoal green #22302A · secondary text #5E6B63 · borders linen #E5DECC.
> **Result colours (only for results):** widely reported = brick red #B5452F · some reports =
> amber #D99A1E · no reports = warm grey #8A8577 · verified business = leaf green #2E8B57.
> Each result colour is used as a 4 px left border + soft tinted background (10% tint) + coloured
> icon, never as a full loud block.
>
> **Type:** headings in a warm serif (Fraunces or Literata), body in Source Sans 3, Hindi in
> Noto Sans Devanagari. Body 17 px on mobile, 16 px on desktop. Big, readable, high contrast.
>
> **Navigation:** top bar with the "Scam Map" wordmark (small map-pin + shield mark in sage),
> an **"EN | हिंदी"** language toggle, and on desktop the links Check · Report · Map · Dashboard ·
> Safety guide · How it works. On mobile a bottom tab bar: Home · Check · Report (raised gold
> button) · Map · More. Footer strip on every page: "Lost money? Call **1930**" (call button) ·
> cybercrime.gov.in · "We never ask for your name or phone number."
>
> **Tone of all text:** simple, kind, never accusing. Say "reported", never "scammer", "fraud" or
> "criminal". No login or sign-up anywhere. Tap targets at least 48 px.

---

## 1. Home
> **Home page.** Hero: serif headline "Check before you trust." and subline "See if a number, UPI ID
> or link has been reported by people near you." Two large equal buttons side by side (stacked on
> mobile): **"Check a number"** (sage, search icon) and **"Report a scam"** (gold outline, flag icon).
> Under them a quick paste box "Paste a number, UPI ID or link" with a Check button.
> An **alert banner** (amber left border): "Scam reports near HSR Layout are higher than usual today".
> A strip of 3 small stat cards: "214 reports this week", "12 areas", "3 new alerts".
> A small "Scam map" preview card (static light map with a few coloured circles) linking to the map.
> A row of 4 scam-type cards from the Safety guide (Digital arrest, Fake KYC link, UPI refund QR,
> Job offer) with icons. Desktop: hero left, map preview right.

## 2. Report a scam (form + success)
> **Report page, a single short form, designed to finish in under 30 seconds.** Title "Report a scam"
> and reassurance "Anonymous. We only save your area, never your name or number."
> **Step 1 "How did they contact you?":** 6 large icon tiles in a 3×2 grid: Phone call · SMS or WhatsApp ·
> QR code · Fake website · UPI request · Something else (selected tile: sage border + tint).
> **Step 2 "When?":** chips Just now / Today / Yesterday (Just now selected).
> **Step 3 "What did they use?":** one big paste box "Number, UPI ID, link or SMS sender" with a
> small chip under it showing the detected type ("Phone number ✓", changeable).
> **Step 4 "Your area":** searchable dropdown "Search area or pincode" (e.g. HSR Layout, 560102) +
> text button "Use my location" with a note "Only your area is saved".
> **Optional, collapsed section "Add details (optional)":** a grid of 12 scam-type icons with labels
> (Digital arrest, Fake KYC link, UPI refund QR, Investment group, Parcel/customs, Job offer,
> Lottery/prize, Loan app threats, Electricity bill, Fake customer care, OTP call, Video call
> blackmail), a short note box "What happened? (in your own words)", "Did you lose money?" amount
> field in ₹, and a toggle "I have a screenshot".
> Full-width sage button **"Report anonymously"**.
> Also design the **success state**: a calm check icon, "Thanks. Reported anonymously.", "Your report
> helps people near you.", buttons "Check another number" and "Lost money? Call 1930".
> Also an **error state** for an invalid number: inline message under the paste box "This doesn't
> look like a valid number. Check and try again."
> Desktop: form in a centred 640 px card, with a side panel "Why report?" + 3 safety tips.
> Also make a **Hindi version** of this page (all labels in Hindi).

## 3. Check a number (lookup + results)
> **Check page.** Big paste box "Paste a number, UPI ID, link or SMS sender" + "Check" button, and a
> type selector (Phone · UPI · Link · SMS sender). Below, a **result card** shown in 4 variants
> (design all four):
> 1) **Widely reported** (brick red): headline "Reported by 7 people near you - be careful",
>    the number shown in full "+91 98765 43210", details: last reported "27 Oct, 6:21 pm",
>    scam type "Digital arrest", areas "HSR Layout, Koramangala".
> 2) **Some reports, not confirmed** (amber): "Some reports, not confirmed", number masked
>    "98XXXXX210" with a small info note "Hidden until 3 different people report it".
> 3) **No reports yet** (warm grey): "No reports yet" + "Still unsure? Don't share OTPs or PINs."
> 4) **Verified business** (leaf green): "Verified business: HDFC Bank customer care".
> Each card has a **safety advice box** for the scam type (e.g. "Police never arrest anyone on a video
> call."), a "Report this number" link, and a 1930 call button. Also a small badge variant
> "Under review - a business disputed these reports". A compact "Recent reports" list under the card
> (date · channel · scam type · area; no names). Desktop: input left, result card right.

## 4. Scam map
> **Map page.** A large, light, Google-Maps-like street map (muted cream/grey basemap) of Bengaluru
> with **semi-transparent circles over areas**, sized by the number of reports and coloured by
> severity (gold = medium, amber = high, brick red = critical). Each circle has a small count label.
> Top: area search "Search area or pincode" and filter chips "Last 7 days · Last 24 hours" and
> "All scam types". An **alert banner** at the top of the map. Legend card (bottom-left): Medium /
> High / Critical. Clicking a circle opens an **area card**: "HSR Layout · 12 reports this week ·
> mostly Digital arrest · High". Mobile: map full screen with a **bottom sheet** listing areas
> (area, count, top scam type, severity pill). Desktop: map left (70%), area list panel right (30%).
> Note on the page: "Circles show areas, never anyone's location."

## 5. Dashboard (city overview)
> **Dashboard page "This week in your city".** City selector (Bengaluru, Mumbai, Delhi...).
> Row of 4 stat cards: Reports this week · Areas affected · New alerts today · Most reported type.
> A simple bar chart "Reports per day (last 7 days)" in sage. A horizontal bar list "Top scam types"
> with icons. A table "Most affected areas" (area, reports, change vs last week with ▲▼, severity pill).
> A list "Latest alerts" (Spike in Bellandur, New scam type in Electronic City: Job offer).
> Flat, clean charts with sage/gold only; no gradients, no 3D. Desktop: 2-column grid; mobile: stacked.

## 6. Safety guide
> **Safety guide page "Know the common scams".** A grid of 12 cards, one per scam type, each with a
> line icon, name, one-line "How it works" and a "What to do" tip: Digital arrest ("Police never
> arrest anyone on a video call"), Fake KYC link ("Banks never ask you to update KYC through an SMS
> link"), UPI refund QR ("You never scan a QR or enter a PIN to receive money"), Investment group,
> Parcel/customs, Job offer, Lottery/prize, Loan app threats, Electricity bill, Fake customer care,
> OTP call ("Never share an OTP with anyone"), Video call blackmail. Tapping a card expands it.
> A highlighted box at the top: "Lost money? Call 1930 within the first hour" + cybercrime.gov.in.
> Language toggle visible; design the Hindi version of 3 cards to check text length.

## 7. How it works & privacy
> **How it works page.** Three-step illustration row (simple line drawings in sage/gold):
> 1 "People report" → 2 "We check the reports are real" → 3 "You see a careful answer".
> Section "How we stop fake reports" with 4 small cards: "One person counts once", "Many accounts on
> one Wi-Fi count once", "Copy-pasted reports count once", "Sudden waves from new accounts are held
> back". Section "Your privacy" with 4 points and icons: "No name or phone number, ever", "Only your
> area is saved, never your location", "Numbers stay hidden until 3 different people report them",
> "We say 'reported', never 'scammer'". Calm, explanatory, lots of white space.

## 8. Business dispute
> **Dispute page "Is this your business number?"** Short intro: "If people reported your real
> business number by mistake, tell us. It will be marked as under review." Form: identifier type +
> value (paste box), business name, contact email, "Proof" note ("GST certificate, shop licence...").
> Button "Submit for review". Success state: "Thanks. This number is now marked as under review."
> Small note: "Your details are only used to review this request and are never shown publicly."

## 9. Licence expired
> **Licence expired screen** (full screen, shown when the service is paused). Centred: a lock icon in
> sage, headline "Licence expired. Contact your provider." and the Hindi line
> "लाइसेंस समाप्त हो गया है। कृपया अपने प्रदाता से संपर्क करें।", a small spinner "Checking again…",
> and the 1930 helpline strip at the bottom. Calm, no red alarm styling.
