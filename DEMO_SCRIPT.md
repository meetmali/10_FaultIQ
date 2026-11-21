# FaultIQ demo script (4 minutes)

A word-for-word script for the INFO 490 Project 2 presentation. It follows the required structure and timing:
intro 20 s, problem and solution 30 s, live demo 120 s, technical 40 s, challenge 20 s, conclusion 10 s.

Slides: the FaultIQ Demo Deck (each slide's speaker notes hold the same lines). Live app:
https://faultiq-web.onrender.com

## Before you record (5 minutes earlier)

1. Open https://faultiq-web.onrender.com once and wait until it loads. The free host sleeps after 15 idle
   minutes and takes 30 to 60 seconds to wake.
2. Log in as `demo` (your `DEMO_PASSWORD`) or a fresh account, so the six sample units are there.
   An older account with no samples: click **Load the sample portfolio** at the bottom of the Overview.
3. Open the **AI assistant** page once and ask any question, so the first real answer is fast.
4. Keep two tabs ready: the slide deck and the app on **Overview**. Browser zoom 110 to 125% so text is readable.
5. Have `web/sample_data/rtu_faulty.csv` handy (it is in the repo) for the optional upload.

Speak at about 150 words a minute. Each section below is sized to its time.

---

## 1. Product introduction (0:00 to 0:20) · Slide 1

> Hi, I'm Meet. This is **FaultIQ**, an AI tool that finds and explains faults in rooftop HVAC units,
> the units that cool most small and mid-size commercial buildings. It's built for facility managers and the
> HVAC technicians who service their equipment.

## 2. Problem and solution (0:20 to 0:50) · Slides 2 and 3

**Slide 2, the problem:**
> Rooftop units fail quietly. A damper sticks, refrigerant leaks, a sensor drifts, and the unit keeps running,
> wasting energy for weeks until someone complains. The data to catch it is already in the building automation
> logs, but small teams don't have time to read them, and enterprise fault-detection software is expensive.

**Slide 3, the solution:**
> FaultIQ reads that trend data, flags abnormal hours with machine learning, names the likely fault with
> physics rules, and gives the technician an AI assistant that ranks causes and what to check first.

## 3. Product demonstration (0:50 to 2:50) · Slide 4, then the live app

Show slide 4 for two seconds ("Input → Processing → Output"), then switch to the app.

**Feature 1: the Overview (0:50 to 1:20)**
- Show the **Overview** page.
> This is the portfolio overview. Six rooftop units on two sites, and their trend data has already been
> analysed. The ring says two of six have no named fault; four have one. Each card shows the unit with the
> faulty part highlighted, here the refrigerant circuit and the outdoor-air damper.

**Feature 2: the complete flow, input → processing → output (1:20 to 2:10)**
- Click **RTU-4** (or any unit) and scroll to **Analyse your own export**.
- Choose `rtu_faulty.csv` and click **Upload and analyse**.
> Here is the full flow. The input is a CSV exported from the building automation system: temperatures,
> damper position and cooling command. When I upload it, Django validates the file, resamples it to hourly
> data, and an Isolation Forest scores every running hour. Physics rules then name what's wrong.
- The analysis page opens (it takes under a second).
> And the output: 294 running hours analysed in about 150 milliseconds. The chart shows supply air against
> its setpoint, with the anomaly score in red. Below are the fault events: economizer not economizing, excess
> outdoor air, low cooling capacity and a mixed-air sensor fault. These are exactly the four faults hidden
> in this test file.
- Click **Insufficient cooling capacity**.
> Each event explains itself: what it means, what to check first, and a review form for the technician.

**Feature 3: the AI assistant (2:10 to 2:50)**
- On the same event page, type in **Ask the AI assistant**:
  `Supply air stays warm even though the compressor runs at 100% on hot afternoons`, then click
  **Rank likely causes**.
> A technician can also describe what they see in plain words. The assistant searches the fault library and
> this team's confirmed past cases. On this free host it runs its lightweight keyword mode; on a bigger
> server it blends in an open-source embedding model. Top match:
> insufficient cooling capacity, with what to check, and a similar case a technician already confirmed:
> a refrigerant leak. If the description doesn't match anything it knows, it says it isn't confident
> instead of guessing.
- Optional if time allows: go back to the event, set **Review** to *Confirmed*, add a note, save.

## 4. Technical implementation (2:50 to 3:30) · Slide 5 (architecture), Slide 6 (AI)

**Slide 5:**
> Under the hood it's one Django 5.2 app on Render with PostgreSQL. Django handles the models, validated
> forms, login so each user sees only their own units, a JSON API and CSV export. The AI runs inside the same
> app: a scikit-learn Isolation Forest detects the faults, and the assistant uses BAAI's open-source bge-small
> embedding model blended with TF-IDF. No external API key, and building data never leaves the server.

**Slide 6:**
> Two AI pieces. Detection is a scikit-learn Isolation Forest plus five physics rules. The assistant blends
> BAAI's bge-small embeddings with TF-IDF. I tested both: the blend got 9 out of 10 top matches right, better
> than embeddings alone at 8.

## 5. Challenges and future improvements (3:30 to 3:50) · Slide 7

> The biggest challenge was false alarms. The first version raised 16 alerts on a perfectly healthy unit,
> because normal morning start-up is rare and the model flags rare. Requiring four hours for any alert no rule
> explains cut false alarms from 25 to 2 without missing a fault. Next, I'll train each unit's model on
> weeks of known-good data and move analysis to a background queue.

## 6. Conclusion (3:50 to 4:00) · Slide 8

> FaultIQ turns raw building data into named, explained faults and next steps in seconds, free and open
> source. Thank you.

---

## If something goes wrong

| Problem | What to do |
|---|---|
| The site is asleep (spinner) | Keep talking over slide 4; it wakes within a minute. Next time, open it beforehand. |
| The upload is slow or fails | Skip it: open the existing analysis from the unit page (**Charts and details →**). Same output. |
| The assistant is slow | The first question after a restart loads the model; the hosted site uses TF-IDF mode, so it is fast. |
| Over time | Drop the optional review step and shorten feature 1. |

## Timing summary

| Section | Time | Slides |
|---|---|---|
| 1. Product introduction | 0:00 to 0:20 | 1 |
| 2. Problem and solution | 0:20 to 0:50 | 2, 3 |
| 3. Product demonstration | 0:50 to 2:50 | 4, then the live app |
| 4. Technical implementation | 2:50 to 3:30 | 5, 6 |
| 5. Challenges and future | 3:30 to 3:50 | 7 |
| 6. Conclusion | 3:50 to 4:00 | 8 |
