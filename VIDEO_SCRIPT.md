# FaultIQ product video script (3 minutes)

The script for the INFO 490 P2-A4 product demonstration. It follows the required structure: startup overview
30 s, live product demonstration 75 s, AI integration 45 s, final product status 30 s. Slides only open and close
the video; everything in between is the live app.

Slides: the FaultIQ Product Video Deck (5 slides; each slide's speaker notes hold the same lines).

Live app: https://faultiq-web.onrender.com

Each step has **Do** (what to click) and **Say** (what to say while you do it). Speak at about 150 words a minute.

## Before you record (5 minutes earlier)

1. Open https://faultiq-web.onrender.com and wait until it loads. The free host sleeps after 15 idle minutes and
   takes up to a minute to wake.
2. **Sign up a fresh account** (off camera), for example `meet_video`. It comes with the six sample units, two work
   orders and one reviewed false alarm, so the screen matches the numbers below. With an older account the
   numbers differ; always say what the screen shows.
3. Two tabs: the deck on slide 1 (full screen) and the app on the **Overview** page. Browser zoom 110 to 125%,
   bookmarks bar hidden. Start the recording on slide 1.
4. Have the assistant sentence ready to paste:
   `Supply air stays warm even though the compressor runs at 100% on hot afternoons`

---

## 1. Startup overview (0:00 to 0:30) · Slides 1 and 2

**Do:** show slide 1 (cover).

**Say:**
> Hi, I'm Meet, and this is FaultIQ, an AI fault detection and diagnostics tool for rooftop HVAC units, the units
> that cool most small and mid-size commercial buildings.

**Do:** go to slide 2 (startup overview).

**Say:**
> When a part fails, like a stuck damper or a refrigerant
> leak, the unit keeps running and quietly wastes energy for weeks. FaultIQ is for facility managers and their
> technicians: it reads the sensor data their buildings already log, finds the fault, and tells them what to fix first.

## 2. Live product demonstration (0:30 to 1:45) · Slide 3 (optional), then the app

**Do:** optionally show slide 3 for two seconds, then switch to the app tab and point at the top of the Overview.

**Say:**
> This is my Overview. I'm logged in, and each account only sees its own buildings. Four of six units have a
> fault, and FaultIQ estimates they waste about 1,800 dollars a month if nobody fixes them.

**Do:** click the **RTU-6** card under "Needs attention".

**Say:**
> Let's open RTU-6. Its sensor data is already analysed, and the drawing highlights the part at fault.

**Do:** click **Charts and details →**.

**Say:**
> It checked 294 running hours in a fraction of a second and found four different faults.

**Do:** click **Insufficient cooling capacity** in the list.

**Say:**
> Each fault says what to check first and what it costs: about 200 dollars a month on this unit.

**Do:** click **Create work order**. Type `Alex` in **Assignee**, then click **Create work order**.

**Say:**
> One click turns it into a work order. FaultIQ suggests the priority from that cost and the detector's
> confidence. I'll assign it and save.

**Do:** click **Work orders** in the top menu.

**Say:**
> The work orders page tracks open, in-progress and finished repairs, overdue dates and the average time to
> repair. Under the hood these are Django models and validated forms. For example, a work order can't be closed
> without repair notes, and the data is also available as a CSV export and a JSON API.

## 3. AI integration (1:45 to 2:30) · Slide 4 (optional), then the app

**Do:** optionally show slide 4 for two seconds. In the app, click **AI assistant** in the top menu. Paste the sentence into the box and click **Rank likely causes**.

**Say:**
> FaultIQ uses two kinds of AI. Detection, which we just saw, is a scikit-learn Isolation Forest plus engineering
> rules. The assistant lets a technician describe a problem in plain words. Its top answer is insufficient cooling
> capacity, with what to check first, plus a similar repair a technician already confirmed. If nothing matches
> well, it says so instead of guessing.

**Do:** under "Was the top answer right?" click **Yes**, then click **AI quality** in the top menu.

**Say:**
> Technicians rate each answer, and the AI quality page tracks how often the AI is right from their own reviews,
> next to my test results: four of four injected faults found, and nine of ten correct top answers.

## 4. Final product status (2:30 to 3:00) · Slide 5

**Do:** switch to the deck and show slide 5 (final product status). End the recording on it.

**Say:**
> What works: the full loop from sensor data to a named fault, its cost, a repair job and AI advice, live on
> Render with all tests passing. The limitations: it's tested on synthetic data, the costs are estimates, and the
> free server runs a lighter keyword version of the assistant. My next priority is a pilot with real data from
> one building to tune the rules. Thank you.

---

## Numbers on a fresh account

| Screen | What it shows |
|---|---|
| Overview | 4 of 6 units have a fault, about $1,813 a month if left unfixed |
| RTU-6 analysis | 294 running hours, 11 fault events, 4 different named faults |
| Insufficient cooling capacity (RTU-6) | 50 kWh so far, about $197 a month, suggested priority Medium |
| Work orders (before you add one) | 0 open, 1 in progress, 1 done, mean time to repair 26 h |
| AI quality | Detector precision 50% (1 confirmed, 1 rejected) before your review |

## If something goes wrong

| Problem | What to do |
|---|---|
| The site is asleep (spinner) | Wait before you start recording; open it 5 minutes early. |
| "Create work order" is a link to an existing work order | You already made one in a rehearsal. Open it and say the same lines, or sign up a new account. |
| Over 3:00 | Shorten the work orders line to "Django models, validated forms, a CSV export and a JSON API." |

## How this covers the grading

| Requirement | Where in the video |
|---|---|
| Problem and target user | Section 1 |
| Primary user workflow | Section 2: Overview → unit → analysis → fault → work order |
| Important Django features | Section 2: login and per-user data, models, form validation, CSV export, JSON API |
| AI processes user input and gives useful results | Section 3: detection results, assistant ranking from typed text, feedback |
| Evaluation and reliability | Section 3: AI quality page and test results; confidence gate |
| What works, limitations, next priority | Section 4 |
