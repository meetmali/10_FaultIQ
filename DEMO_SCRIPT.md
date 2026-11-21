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

Show slide 4 for two seconds, then switch to the app tab. Each feature below has **Do** (what to click) and
**Say** (what to say while you do it).

### Feature 1: The home page (0:50 to 1:20)

**Do:** click **Overview** in the top menu.

**Say:**
> This is the home page of FaultIQ, and it gives an overview of all the faulty equipment in the building's
> HVAC system. Here we have seven rooftop units, and four of them have a fault. The chart on the right shows
> which faults take up the most hours. Each card shows a unit with its faulty part highlighted in red, so you
> can see at a glance where the problem is. Units marked **Check** look unusual and are worth a closer look.

### Feature 2: Looking inside one unit (1:20 to 2:10)

No upload needed: this unit's data is already loaded and analysed.

**Do:** click the **RTU-6** card.

**Say:**
> Let's open one unit. RTU-6's sensor data came in as a CSV file, the kind of file a building system already
> exports. FaultIQ checked the file, its AI model looked at every hour the unit was running to spot unusual
> behaviour, and simple engineering rules then named the fault. The drawing shows exactly which part is
> affected.

**Do:** click **Charts and details →** (next to "Fault events in the latest analysis").

**Say:**
> Here's the full result. It analysed almost 300 hours of data in under a second. The chart shows the supply
> air temperature against its target, and the red line shows how unusual each hour looks. Below, FaultIQ
> found four different faults, the same four we hid in this test data.

**Do:** click **Insufficient cooling capacity** in the list.

**Say:**
> When I open one, it explains what the fault means and what the technician should check first.

### Feature 3: Asking the AI assistant (2:10 to 2:50)

**Do:**
1. On the same page, find the box **Ask the AI assistant**.
2. Type: `Supply air stays warm even though the compressor runs at 100% on hot afternoons`
3. Click **Rank likely causes**.

**Say:**
> Technicians can also describe a problem in their own words. I'll type what I'd see on site: the supply air
> stays warm even though the compressor is running at full power. The AI assistant compares this with our
> fault library and with past cases a technician already confirmed. Its top answer is insufficient cooling
> capacity, and it tells me exactly what to check. If it isn't sure, it says so instead of guessing.

**Optional, if you have time:** go back to the fault, set **Review status** to *Confirmed*, type a short note
and click **Save review**.

(The numbers above match the `meetmali` account with seven units. On a fresh account or `demo` there are six;
always say what the screen shows.)

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
| A page is slow | Keep talking; pages load within a few seconds once the site is awake. |
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
